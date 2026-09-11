# B1 independent source: C0 parents plus explicitly budgeted opportunity sensing.
"""Black-box, serial source search; no simulator internals are accessed.

Only Python's standard library is required.  The env object supplies four
methods: enter(), measure(x,y,channel), clear(x,y,channel), exit().
"""
import json
import math
import os
import time

_sp_EPS = math.radians(1.005001)  # bounded error plus rounding to two decimals
_sp_VIRTUAL_SAFE_SWITCH_S = 180000.0  # common to optimized and baseline policies

_sp_BASELINE_CONFIG = dict(advance_fraction=.78,lateral_fraction=.20,clear_trial_radius=42,
                       route_optimization=False,upper_bound_stop=False,rescue_initial_clear=True,
                       joint_scheduling=False,clear_standoff=False)
_sp_OPTIMIZED_CONFIGS = {
    3: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.55,clear_standoff=True),
    4: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.60,clear_standoff=True),
}


def _sp_dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _sp_clip(poly, a, b, c):
    """Intersection with closed half-plane a*x+b*y <= c."""
    if not poly:
        return []
    result = []
    p = poly[-1]
    fp = a * p[0] + b * p[1] - c
    for q in poly:
        fq = a * q[0] + b * q[1] - c
        if (fp <= 1e-8) != (fq <= 1e-8):
            t = fp / (fp - fq)
            result.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        if fq <= 1e-8:
            result.append(q)
        p, fp = q, fq
    return result


def _sp_initial_polygon():
    # Circumscription, not inscription: the true disk is never cut away.
    radius = 1800 / math.cos(math.pi / 48)
    return [(radius * math.cos(2 * math.pi * i / 48),
             radius * math.sin(2 * math.pi * i / 48)) for i in range(48)]


def _sp_add_bearing(poly, p, deg):
    lo, hi = math.radians(deg) - _sp_EPS, math.radians(deg) + _sp_EPS
    # cross(u_lo, target-p)>=0; cross(u_hi, target-p)<=0.
    for a, b in [(math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))]:
        poly = _sp_clip(poly, a, b, a * p[0] + b * p[1])
    # Effective receive radius is at most 1500; tangent half-planes preserve it.
    for i in range(24):
        a, b = math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24)
        poly = _sp_clip(poly, a, b, 1500 + a * p[0] + b * p[1])
    return poly


def _sp_circle_of_three(a, b, c):
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    dd = 2 * (bx * cy - by * cx)
    if abs(dd) < 1e-10:
        return None
    ub = bx * bx + by * by
    uc = cx * cx + cy * cy
    center = (a[0] + (cy * ub - by * uc) / dd,
              a[1] + (bx * uc - cx * ub) / dd)
    return center, _sp_dist(center, a)


def _sp_enclosing_circle(poly):
    """Exact finite-vertex minimum enclosing circle, deterministic incremental."""
    if not poly:
        raise RuntimeError('Empty feasible polygon; observations violate the error bound')
    center, radius = poly[0], 0.0
    for i, p in enumerate(poly):
        if _sp_dist(center, p) <= radius + 1e-7:
            continue
        center, radius = p, 0.0
        for j in range(i):
            q = poly[j]
            if _sp_dist(center, q) <= radius + 1e-7:
                continue
            center = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            radius = _sp_dist(p, q) / 2
            for k in range(j):
                r = poly[k]
                if _sp_dist(center, r) > radius + 1e-7:
                    candidate = _sp_circle_of_three(p, q, r)
                    if candidate is not None:
                        center, radius = candidate
    # Conservative recheck protects the clearing certificate from roundoff.
    return center, max(_sp_dist(center, p) for p in poly)


def _sp_certified_points(mode):
    """Analytic source of the certificate, independent of external JSON data."""
    if mode == 3:
        # The source radius r is either <=1000 (origin detects it), or
        # in [1000,1800] with angle <=pi/6 to one of these six stations.
        # d(r)^2=r*r+rr*rr-2*r*rr*cos(pi/6) is convex in r.  At both
        # endpoints it is <1000^2 for rr=1124.  Thus all source positions
        # are detectable.  Moving the ring inward shortens mandatory travel.
        rr = 1124.0
        return [(0.0, 0.0)] + [(rr * math.cos(i * math.pi / 3), rr * math.sin(i * math.pi / 3)) for i in range(6)]
    # Seven sectors, each split into four triangles.  The outer heptagon
    # contains the 1800 m target disk; every elementary edge is <1000 m.
    rr=999.5
    inner=[(rr*math.cos(2*math.pi*k/7),rr*math.sin(2*math.pi*k/7)) for k in range(7)]
    outer=[(2*p[0],2*p[1]) for p in inner]
    midpoint=[(inner[k][0]+inner[(k+1)%7][0],inner[k][1]+inner[(k+1)%7][1]) for k in range(7)]
    return [(0.0,0.0)]+inner+outer+midpoint


def _sp_default_points(mode):
    if mode == 3:
        return _sp_certified_points(mode)
    filename=os.path.join(os.path.dirname(__file__),'coverage_points.json')
    if os.path.exists(filename):
        with open(filename,encoding='utf-8') as stream:
            supplied=json.load(stream)
        return [tuple(p) for p in supplied['q'+str(mode)]]
    return _sp_certified_points(mode)


class _sp_Solver:
    def __init__(self, env, mode=3, **config):
        self.env, self.mode, self.config = env, int(mode), config
        if self.mode not in (3,4):
            raise ValueError('mode must be 3 or 4')
        self.config={**_sp_OPTIMIZED_CONFIGS[self.mode],**config}
        self.position = (0.0, 0.0)
        self.channel = 1
        self.cleared = set()
        self.observations = {c: [] for c in range(1,21)}
        self.polygons = {}
        self.scanned = {c: set() for c in range(1,21)}
        self.no_signal_points = {c: [] for c in range(1,21)}
        self.counters = {'measure':0, 'clear_attempts':0, 'fallbacks':0, 'failed_clear':0,
                         'localization_moves':0, 'scan_stations':0,'certified_clear_attempts':0,
                         'heuristic_clear_attempts':0,'budget_fallbacks':0}
        self.virtual_time = 0.0
        self.deadline = None
        self.trace = []
        self.points = config.get('points') or _sp_default_points(self.mode)
        self.points = [tuple(map(float,p)) for p in self.points]
        certified=_sp_certified_points(self.mode)
        fingerprint=lambda points: sorted((round(p[0],7),round(p[1],7)) for p in points)
        if fingerprint(self.points)!=fingerprint(certified):
            raise ValueError('Custom search points lack the required geometric coverage certificate')

    def _accept(self, result):
        if result.get('accepted') is not True:
            raise RuntimeError('Action rejected: ' + repr(result))
        self.virtual_time = float(result.get('virtual_time_s', self.virtual_time))
        return result

    def measure(self, p, ch):
        self._time_guard()
        p = tuple(map(float,p))
        r = self._accept(self.env.measure(p[0],p[1],int(ch)))
        self.position, self.channel = p, ch
        self.counters['measure'] += 1
        kind = r['measure_result']
        self.trace.append({'action':'measure','x':p[0],'y':p[1],'channel':ch,'result':kind,
                           'svd_deg':r.get('svd_deg'),'virtual_time_s':self.virtual_time})
        if kind == 'direction':
            deg = float(r['svd_deg'])
            self.observations[ch].append((p,deg))
            self.polygons[ch] = _sp_add_bearing(self.polygons.get(ch,_sp_initial_polygon()),p,deg)
            if not self.polygons[ch]:
                raise RuntimeError('Inconsistent measured bearing constraints')
        elif kind == 'near':
            self.clear(p,ch,certified=True)
        elif kind == 'no_signal':
            self.no_signal_points[ch].append(p)
        else:
            raise RuntimeError('Unknown measurement result: '+str(kind))
        return kind

    def clear(self,p,ch,certified=False):
        self._time_guard()
        p = tuple(map(float,p))
        r = self._accept(self.env.clear(p[0],p[1],int(ch)))
        self.position = p
        self.counters['clear_attempts'] += 1
        self.counters['certified_clear_attempts' if certified else 'heuristic_clear_attempts'] += 1
        success = r['clear_result'] == 'success'
        if success:
            self.cleared.add(ch)
        else:
            self.counters['failed_clear'] += 1
        self.trace.append({'action':'clear','x':p[0],'y':p[1],'channel':ch,
                           'result':r['clear_result'],'certified_before_action':certified,
                           'virtual_time_s':self.virtual_time})
        if certified and not success:
            raise RuntimeError('Certified optical clear failed: observations/environment violate the stated model')
        return success

    def _time_guard(self):
        if self.deadline and time.monotonic() > self.deadline:
            raise TimeoutError('Remaining real-time budget nearly exhausted; completeness not certified')

    def _virtual_fallback(self,ch):
        """Preserve the virtual-time reserve; this is never an exit certificate."""
        if self.virtual_time >= _sp_VIRTUAL_SAFE_SWITCH_S:
            self.counters['budget_fallbacks'] += 1
            self.cover_polygon(ch)
            return True
        return False

    def second_point(self,ch):
        p, deg = self.observations[ch][-1]
        theta = math.radians(deg)
        ux,uy = math.cos(theta),math.sin(theta)
        center,radius = _sp_enclosing_circle(self.polygons[ch])
        length = max(0,(center[0]-p[0])*ux+(center[1]-p[1])*uy)
        # The candidate moves mostly toward the source, adding enough lateral
        # baseline to resolve range while avoiding a long out-and-back detour.
        advance = max(30, length * self.config.get('advance_fraction',0.78))
        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.20)))
        candidates = [(p[0]+advance*ux+sign*lateral*(-uy),
                       p[1]+advance*uy+sign*lateral*ux) for sign in [-1,1]]
        # Favor candidate nearer the other planned search stations, a cheap
        # approximation to downstream route cost, with deterministic tie-break.
        return min(candidates,key=lambda q: (_sp_dist(q,self.position) + 0.12*min(_sp_dist(q,w) for w in self.points),q))

    def route_clear_point(self, center, radius, original):
        """Shorten the predicted entry+exit path inside a certified clear disk.

        If polygon lies in B(center,radius), every point in
        B(center,20-radius) is <=20 m from every feasible source. Only this
        feasible disk is optimized. The next route point is a forecast, so
        its shorter surrogate path is not claimed as global online optimality.
        """
        target=getattr(self,'route_successor',None)
        margin=max(0.0,20-radius-1e-6)
        if target is None or margin<=1e-6:
            return original
        start=self.position
        if _sp_dist(start,center)<=margin:
            return start
        def cost(p):return _sp_dist(start,p)+_sp_dist(p,target)
        vx,vy=target[0]-start[0],target[1]-start[1]
        dx,dy=start[0]-center[0],start[1]-center[1]
        aa=vx*vx+vy*vy;bb=2*(dx*vx+dy*vy)
        cc=dx*dx+dy*dy-margin*margin
        candidates=[original,center]
        disc=bb*bb-4*aa*cc
        if aa>1e-12 and disc>=0:
            low=(-bb-math.sqrt(disc))/(2*aa)
            high=(-bb+math.sqrt(disc))/(2*aa)
            if low<=1 and high>=0:
                t=max(0.0,low)
                candidates.append((start[0]+t*vx,start[1]+t*vy))
        step=2*math.pi/32
        point=lambda a:(center[0]+margin*math.cos(a),center[1]+margin*math.sin(a))
        best_angle=min(range(32),key=lambda i:cost(point(i*step)))*step
        lo,hi=best_angle-step,best_angle+step
        golden=(math.sqrt(5)-1)/2
        a=hi-golden*(hi-lo);b=lo+golden*(hi-lo)
        fa,fb=cost(point(a)),cost(point(b))
        for _ in range(28):
            if fa<=fb:
                hi,b,fb=b,a,fa;a=hi-golden*(hi-lo);fa=cost(point(a))
            else:
                lo,a,fa=a,b,fb;b=lo+golden*(hi-lo);fb=cost(point(b))
        candidates.extend([point(a),point(b)])
        # A numerical feasibility recheck preserves the pre-existing margin.
        feasible=[p for p in candidates if _sp_dist(p,center)<=margin+1e-8]
        return min(feasible,key=cost) if feasible else original

    def localize(self,ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations',9))
        for k in range(max_iter):
            if self._virtual_fallback(ch):
                return
            center,radius = _sp_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius',100.0) or k >= 3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=_sp_dist(self.position,center)
                    margin=max(0,20-radius-1e-6)
                    if distance<=margin:
                        clear_point=self.position
                    elif distance>0:
                        clear_point=(center[0]+margin*(self.position[0]-center[0])/distance,
                                     center[1]+margin*(self.position[1]-center[1])/distance)
                if radius<=20 and self.config.get('route_clear',True):
                    clear_point=self.route_clear_point(center,radius,clear_point)
                if self.clear(clear_point,ch,certified=radius<=20):
                    return
                if self._virtual_fallback(ch):
                    return
                # A measurement at a failed optical attempt adds no movement.
                kind = self.measure(center,ch)
                if ch in self.cleared:
                    return
                if self._virtual_fallback(ch):
                    return
                if kind == 'direction':
                    continue
                if self.rescue_bearing(ch,k):
                    if ch in self.cleared:
                        return
                    continue
                if self._virtual_fallback(ch):
                    return
            if len(self.observations[ch]) == 1:
                q = self.second_point(ch)
            else:
                # At this distance ±1 degree amounts to only a few metres;
                # moving toward the feasible-set center quickly shrinks it.
                p,deg = self.observations[ch][-1]
                dd = _sp_dist(p,center)
                if dd < 25:
                    theta = math.radians(deg)+math.pi/2
                    q = (p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:
                    q = center
            # Do not average the same-location, fixed environmental error.
            if any(_sp_dist(q,p)<1e-5 for p,d in self.observations[ch]):
                q = (q[0]+23.0,q[1]+17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q,ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                # Optical clearing is independent of antenna direction.
                center,radius = _sp_enclosing_circle(self.polygons[ch])
                if (len(self.observations[ch])>=2 or radius<=100 or
                        self.config.get('rescue_initial_clear',False)):
                    if self.clear(center,ch):
                        return
                    if self._virtual_fallback(ch):
                        return
                self.rescue_bearing(ch,k)
                if ch in self.cleared:
                    return
        self.cover_polygon(ch)

    def rescue_bearing(self,ch,iteration=0):
        """Recover a bearing near a previously visible point after RF loss.

        A full ring is explored if necessary.  This is a speed heuristic;
        completeness comes from the finite optical polygon cover, not an
        assumption that a directional source remains visible after movement.
        """
        p,deg=min(self.observations[ch],key=lambda z:_sp_dist(z[0],self.position))
        angle=math.radians(deg)
        rr=80.0+iteration*11.0
        angles=[70,-70,110,-110,35,-35,0,180,145,-145,20,-20,90,-90,160,-160]
        for offset in angles:
            if self.virtual_time >= _sp_VIRTUAL_SAFE_SWITCH_S:
                return False
            a=angle+math.radians(offset)
            q=(p[0]+rr*math.cos(a),p[1]+rr*math.sin(a))
            if any(_sp_dist(q,old)<1e-6 for old,d in self.observations[ch]):
                continue
            kind=self.measure(q,ch)
            if kind in ('direction','near'):
                return True
        return False

    def cover_polygon(self,ch):
        """Finite optical cover of the retained polygon; independent of RF direction.

        Every point belongs to a 25 m square centered on this lattice, and is
        at most 25/sqrt(2)<20 m from its center.  Include each cell whose
        bounding box intersects the polygon.  This fallback is conservative.
        """
        self.counters['fallbacks'] += 1
        poly = self.polygons[ch]
        # Rotate coordinates along the first bearing, making the narrow wedge
        # bounding rectangle far smaller than its axis-aligned rectangle.
        origin,deg=self.observations[ch][0]
        angle=math.radians(deg)
        u=(math.cos(angle),math.sin(angle)); v=(-u[1],u[0])
        local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
                (p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in poly]
        spacing=25.0
        lo=[math.floor((min(p[d] for p in local)-spacing/2)/spacing) for d in [0,1]]
        hi=[math.ceil((max(p[d] for p in local)+spacing/2)/spacing) for d in [0,1]]
        candidates=[]
        for i in range(lo[0],hi[0]+1):
            row=range(lo[1],hi[1]+1) if i%2==0 else range(hi[1],lo[1]-1,-1)
            for j in row:
                test=local
                for a,b,c in [(1,0,(i+.5)*spacing),(-1,0,(-i+.5)*spacing),
                              (0,1,(j+.5)*spacing),(0,-1,(-j+.5)*spacing)]:
                    test=_sp_clip(test,a,b,c)
                if test:
                    candidates.append((origin[0]+i*spacing*u[0]+j*spacing*v[0],
                                       origin[1]+i*spacing*u[1]+j*spacing*v[1]))
        # Keep the constructed column snake.  Convexity makes occupied columns
        # consecutive.  At most 62 columns x 3 rows are possible, and every
        # inter-column step is <=25*sqrt(5), giving a finite path-length bound.
        for point in candidates:
            if self.clear(point,ch):
                return
        raise RuntimeError('Finite optical covering exhausted without success: model mismatch')

    def scan_station(self,index,defer=False):
        p=self.points[index]
        unknown=[c for c in range(1,21) if c not in self.cleared and not self.observations[c]]
        if self.channel in unknown:
            unknown.remove(self.channel); unknown.insert(0,self.channel)
        self.counters['scan_stations'] += 1
        for ch in unknown:
            self.measure(p,ch)
            self.scanned[ch].add(index)
        if (self.mode == 3 and index == 0 and not self.cleared and
                not any(self.observations.values()) and
                self.config.get('adaptive_ring',True) and
                not any(i != 0 for indices in self.scanned.values() for i in indices)):
            # All channels were silent at the origin, so every real source is
            # farther than 1000 m.  Choose the equally certified outer ring
            # before any non-origin station is visited.  This does not infer
            # source count or terminate search; only the route geometry changes.
            # Both rings satisfy max_{r in [1000,1800]} d(r) < 1000.
            rr=1800*math.cos(math.pi/6)
            self.points=[(0.0,0.0)]+[(rr*math.cos(i*math.pi/3),
                                      rr*math.sin(i*math.pi/3)) for i in range(6)]
        pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
        if defer:
            for ch in pending:
                if any(_sp_dist(p,old)<1e-5 for old,d in self.observations[ch]):
                    continue
                center,radius=_sp_enclosing_circle(self.polygons[ch])
                if _sp_dist(center,p)<=1500+radius:
                    self.measure(p,ch)
            return
        while pending:
            ch=min(pending,key=lambda c:_sp_dist(self.position,_sp_enclosing_circle(self.polygons[c])[0]))
            self.localize(ch)
            pending.remove(ch)

    def next_station(self,todo):
        if not self.config.get('route_optimization',True) or len(todo)<3:
            return min(todo,key=lambda i:_sp_dist(self.position,self.points[i]))
        remaining=set(todo); greedy=[]; p=self.position
        while remaining:
            i=min(remaining,key=lambda i:_sp_dist(p,self.points[i]))
            greedy.append(i); remaining.remove(i); p=self.points[i]
        def length(route):
            return _sp_dist(self.position,self.points[route[0]])+sum(
                _sp_dist(self.points[a],self.points[b]) for a,b in zip(route,route[1:]))
        def improve(route):
            route=route[:]
            for iteration in range(60):
                change=0; best=None
                for i in range(len(route)-1):
                    before=self.position if i==0 else self.points[route[i-1]]
                    for j in range(i+1,len(route)):
                        a,b=self.points[route[i]],self.points[route[j]]
                        delta=_sp_dist(before,b)-_sp_dist(before,a)
                        if j+1<len(route):
                            after=self.points[route[j+1]]
                            delta+=_sp_dist(a,after)-_sp_dist(b,after)
                        if delta<change-1e-7:
                            change,best=delta,(i,j)
                if best is None:
                    break
                i,j=best; route[i:j+1]=reversed(route[i:j+1])
            return route
        candidates=[improve(greedy),improve(sorted(todo)),improve(sorted(todo,reverse=True))]
        return min(candidates,key=length)[0]

    def spatial_next_task(self, todo):
        """Receding-horizon open tour of certified stations and known regions.

        Source centers are estimates used only for route ordering. They are
        never optical certificates; localization still uses its bounded set.
        Every route contains each remaining station and each pending source.
        """
        tasks=[('station',i) for i in sorted(todo)]+[
            ('source',c) for c in range(1,21)
            if self.observations[c] and c not in self.cleared]
        positions=[self.position]+[
            self.points[k] if kind=='station' else _sp_enclosing_circle(self.polygons[k])[0]
            for kind,k in tasks]
        n=len(tasks)
        ds=[[_sp_dist(a,b) for b in positions] for a in positions]
        remaining=set(range(1,n+1));greedy=[];p=0
        while remaining:
            q=min(remaining,key=lambda j:(ds[p][j],j))
            greedy.append(q);remaining.remove(q);p=q
        def improve(route):
            route=route[:]
            for _ in range(60):
                best=None;delta=0.
                for i in range(n-1):
                    before=0 if i==0 else route[i-1]
                    a=route[i]
                    for j in range(i+1,n):
                        b=route[j]
                        change=ds[before][b]-ds[before][a]
                        if j+1<n:
                            after=route[j+1];change+=ds[a][after]-ds[b][after]
                        if change<delta-1e-7:delta=change;best=(i,j)
                if best is None:break
                i,j=best;route[i:j+1]=reversed(route[i:j+1])
            return route
        # Multiple deterministic starts guard against short-sighted nearest
        # neighbor choices while keeping the total cost tied to physical metres.
        starts=[greedy,list(range(1,n+1)),list(range(n,0,-1))]
        routes=[improve(x) for x in starts]
        def reinsert(route):
            route=route[:]
            for _ in range(30):
                best=None;delta=0.
                for i,x in enumerate(route):
                    before=0 if i==0 else route[i-1]
                    after=route[i+1] if i+1<n else None
                    remove=-ds[before][x]
                    if after is not None:remove+=ds[before][after]-ds[x][after]
                    short=route[:i]+route[i+1:]
                    for j in range(n):
                        if j==i:continue
                        left=0 if j==0 else short[j-1]
                        right=short[j] if j<len(short) else None
                        change=remove+ds[left][x]
                        if right is not None:change+=ds[x][right]-ds[left][right]
                        if change<delta-1e-7:best=(i,j);delta=change
                if best is None:break
                i,j=best;x=route.pop(i);route.insert(j,x)
                route=improve(route)
            return route
        # Keep every original 2-opt tour as well: extra search cannot worsen
        # the fixed-state distance proxy, although online realized cost may vary.
        routes+= [reinsert(x) for x in routes]
        length=lambda r:ds[0][r[0]]+sum(ds[a][b] for a,b in zip(r,r[1:]))
        best=min(routes,key=lambda r:(length(r),r))
        self.route_successor=positions[best[1]] if len(best)>1 else None
        return tasks[best[0]-1]

    def all_sources_discovered(self):
        """Observed distinct channels saturate the public upper bound of 16.

        Positive bearing/near/clear feedback is required for every counted
        channel.  This establishes discovery, never successful clearance.
        """
        known=self.cleared | {c for c in range(1,21) if self.observations[c]}
        return len(known)>=16

    def run(self):
        started=time.monotonic()
        entered=self._accept(self.env.enter())
        remaining=float(entered.get('remaining_real_duration_s',1200))
        self.deadline=started+max(0,remaining-5)
        todo=set(range(len(self.points)))
        visited=[]
        while todo or any(self.observations[c] and c not in self.cleared for c in range(1,21)):
            if todo and self.all_sources_discovered():
                # No possible unseen emitter remains; retain all pending
                # localization work and the final 16-success exit certificate.
                self.counters['stations_waived_after_all_discovered']=len(todo)
                todo.clear()
            self.route_successor=None
            pending=[c for c in range(1,21)
                     if self.observations[c] and c not in self.cleared]
            # In mode 4 an early bearing wedge can be long and its center
            # a poor future route endpoint.  Use the global spatial tour only
            # after every pending region fits the existing optical-trial scale.
            # This is route eligibility, not a clearing or absence certificate.
            ready=(self.mode == 3 or (pending and all(
                _sp_enclosing_circle(self.polygons[c])[1] <=
                self.config.get('clear_trial_radius',100) for c in pending)))
            if ready and self.config.get('spatial_route',True):
                kind,key=self.spatial_next_task(todo)
                if kind=='source':
                    self.localize(key)
                else:
                    self.scan_station(key,defer=True)
                    visited.append(key);todo.remove(key)
                if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                    break
                continue
            if self.config.get('joint_scheduling',False):
                pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
                index=self.next_station(todo) if todo else None
                if pending:
                    ch=min(pending,key=lambda c:_sp_dist(self.position,_sp_enclosing_circle(self.polygons[c])[0]))
                    target=_sp_enclosing_circle(self.polygons[ch])[0]
                    source_cost=_sp_dist(self.position,target)*self.config.get('source_priority',1.0)
                    station_cost=(_sp_dist(self.position,self.points[index]) if index is not None else float('inf'))
                    if source_cost<=station_cost:
                        self.localize(ch)
                        if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                            break
                        continue
                self.scan_station(index,defer=True)
                visited.append(index);todo.remove(index)
                if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                    break
                continue
            index=self.next_station(todo)
            self.scan_station(index)
            visited.append(index); todo.remove(index)
            if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                break
        unresolved=[c for c in range(1,21) if c not in self.cleared]
        count_certificate=len(self.cleared)>=16
        geometric_certificate=all(not self.observations[c] and len(self.scanned[c])==len(self.points)
                                  for c in unresolved)
        certificate=count_certificate or geometric_certificate
        if not certificate:
            raise RuntimeError('Search ended without complete coverage certificate')
        final=self._accept(self.env.exit())
        return {'mode':self.mode,'cleared_count':len(self.cleared),'cleared_channels':sorted(self.cleared),
                'virtual_time_s':self.virtual_time,'average_time_s':self.virtual_time/max(1,len(self.cleared)),
                'program_time_s':time.monotonic()-started,'coverage_complete':certificate,
                'completion_certified':certificate,'geometric_coverage_complete':geometric_certificate,
                'coverage_point_count':len(self.points),'visited_points':visited,
                'certificate_type':'known_count_upper_bound' if count_certificate else 'complete_geometric_coverage',
                'unresolved_channels_certified_absent':unresolved,'counters':dict(self.counters),
                'exit_response':final}


"""Black-box, serial source search; no simulator internals are accessed.

Only Python's standard library is required.  The env object supplies four
methods: enter(), measure(x,y,channel), clear(x,y,channel), exit().
"""
import json
import math
import os
import time

_di_EPS = math.radians(1.005001)  # bounded error plus rounding to two decimals
_di_VIRTUAL_SAFE_SWITCH_S = 180000.0  # common to optimized and baseline policies

_di_BASELINE_CONFIG = dict(advance_fraction=.78,lateral_fraction=.20,clear_trial_radius=42,
                       route_optimization=False,upper_bound_stop=False,rescue_initial_clear=True,
                       joint_scheduling=False,clear_standoff=False)
_di_OPTIMIZED_CONFIGS = {
    3: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.55,clear_standoff=True),
    4: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.60,clear_standoff=True),
}


def _di_dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _di_clip(poly, a, b, c):
    """Intersection with closed half-plane a*x+b*y <= c."""
    if not poly:
        return []
    result = []
    p = poly[-1]
    fp = a * p[0] + b * p[1] - c
    for q in poly:
        fq = a * q[0] + b * q[1] - c
        if (fp <= 1e-8) != (fq <= 1e-8):
            t = fp / (fp - fq)
            result.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        if fq <= 1e-8:
            result.append(q)
        p, fp = q, fq
    return result


def _di_initial_polygon():
    # Circumscription, not inscription: the true disk is never cut away.
    radius = 1800 / math.cos(math.pi / 48)
    return [(radius * math.cos(2 * math.pi * i / 48),
             radius * math.sin(2 * math.pi * i / 48)) for i in range(48)]


def _di_add_bearing(poly, p, deg):
    lo, hi = math.radians(deg) - _di_EPS, math.radians(deg) + _di_EPS
    # cross(u_lo, target-p)>=0; cross(u_hi, target-p)<=0.
    for a, b in [(math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))]:
        poly = _di_clip(poly, a, b, a * p[0] + b * p[1])
    # Effective receive radius is at most 1500; tangent half-planes preserve it.
    for i in range(24):
        a, b = math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24)
        poly = _di_clip(poly, a, b, 1500 + a * p[0] + b * p[1])
    return poly


def _di_circle_of_three(a, b, c):
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    dd = 2 * (bx * cy - by * cx)
    if abs(dd) < 1e-10:
        return None
    ub = bx * bx + by * by
    uc = cx * cx + cy * cy
    center = (a[0] + (cy * ub - by * uc) / dd,
              a[1] + (bx * uc - cx * ub) / dd)
    return center, _di_dist(center, a)


def _di_enclosing_circle(poly):
    """Exact finite-vertex minimum enclosing circle, deterministic incremental."""
    if not poly:
        raise RuntimeError('Empty feasible polygon; observations violate the error bound')
    center, radius = poly[0], 0.0
    for i, p in enumerate(poly):
        if _di_dist(center, p) <= radius + 1e-7:
            continue
        center, radius = p, 0.0
        for j in range(i):
            q = poly[j]
            if _di_dist(center, q) <= radius + 1e-7:
                continue
            center = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            radius = _di_dist(p, q) / 2
            for k in range(j):
                r = poly[k]
                if _di_dist(center, r) > radius + 1e-7:
                    candidate = _di_circle_of_three(p, q, r)
                    if candidate is not None:
                        center, radius = candidate
    # Conservative recheck protects the clearing certificate from roundoff.
    return center, max(_di_dist(center, p) for p in poly)


def _di_certified_points(mode):
    """Analytic source of the certificate, independent of external JSON data."""
    if mode == 3:
        rr = 1800 * math.cos(math.pi / 6)
        return [(0.0, 0.0)] + [(rr * math.cos(i * math.pi / 3), rr * math.sin(i * math.pi / 3)) for i in range(6)]
    # B3: exact-decimal 21-station continuous half-plane coverage certificate.
    # Each certified quadtree leaf lies in the convex hull of stations all
    # within 1000m of the entire leaf; at least one is in every closed
    # emission half-plane. See research/certificate_21_999_1864.json.
    return [[0.0, 0.0], [999.0, 0.0], [706.399674, 706.399674], [0.0, 999.0], [-706.399674, 706.399674], [-999.0, 0.0], [-706.399674, -706.399674], [-0.0, -999.0], [706.399674, -706.399674], [1864.0, 0.0], [1614.271353, 932.0], [932.0, 1614.271353], [0.0, 1864.0], [-932.0, 1614.271353], [-1614.271353, 932.0], [-1864.0, 0.0], [-1614.271353, -932.0], [-932.0, -1614.271353], [-0.0, -1864.0], [932.0, -1614.271353], [1614.271353, -932.0]]


def _di_default_points(mode):
    filename=os.path.join(os.path.dirname(__file__),'coverage_points.json')
    if os.path.exists(filename):
        with open(filename,encoding='utf-8') as stream:
            supplied=json.load(stream)
        return [tuple(p) for p in supplied['q'+str(mode)]]
    return _di_certified_points(mode)


class _di_Solver:
    def __init__(self, env, mode=3, **config):
        self.env, self.mode, self.config = env, int(mode), config
        if self.mode not in (3,4):
            raise ValueError('mode must be 3 or 4')
        self.config={**_di_OPTIMIZED_CONFIGS[self.mode],**config}
        self.position = (0.0, 0.0)
        self.channel = 1
        self.cleared = set()
        self.observations = {c: [] for c in range(1,21)}
        self.polygons = {}
        self.scanned = {c: set() for c in range(1,21)}
        self.no_signal_points = {c: [] for c in range(1,21)}
        self.counters = {'measure':0, 'clear_attempts':0, 'fallbacks':0, 'failed_clear':0,
                         'localization_moves':0, 'scan_stations':0,'certified_clear_attempts':0,
                         'heuristic_clear_attempts':0,'budget_fallbacks':0}
        self.virtual_time = 0.0
        self.deadline = None
        self.trace = []
        self._visibility_cache = {}
        self.points = config.get('points') or _di_default_points(self.mode)
        self.points = [tuple(map(float,p)) for p in self.points]
        certified=_di_certified_points(self.mode)
        fingerprint=lambda points: sorted((round(p[0],7),round(p[1],7)) for p in points)
        if fingerprint(self.points)!=fingerprint(certified):
            raise ValueError('Custom search points lack the required geometric coverage certificate')

    def _accept(self, result):
        if result.get('accepted') is not True:
            raise RuntimeError('Action rejected: ' + repr(result))
        self.virtual_time = float(result.get('virtual_time_s', self.virtual_time))
        return result

    def measure(self, p, ch):
        self._time_guard()
        p = tuple(map(float,p))
        r = self._accept(self.env.measure(p[0],p[1],int(ch)))
        self.position, self.channel = p, ch
        self.counters['measure'] += 1
        kind = r['measure_result']
        self.trace.append({'action':'measure','x':p[0],'y':p[1],'channel':ch,'result':kind,
                           'svd_deg':r.get('svd_deg'),'virtual_time_s':self.virtual_time})
        if kind == 'direction':
            deg = float(r['svd_deg'])
            self.observations[ch].append((p,deg))
            self.polygons[ch] = _di_add_bearing(self.polygons.get(ch,_di_initial_polygon()),p,deg)
            if not self.polygons[ch]:
                raise RuntimeError('Inconsistent measured bearing constraints')
        elif kind == 'near':
            self.clear(p,ch,certified=True)
        elif kind == 'no_signal':
            self.no_signal_points[ch].append(p)
        else:
            raise RuntimeError('Unknown measurement result: '+str(kind))
        return kind

    def clear(self,p,ch,certified=False):
        self._time_guard()
        p = tuple(map(float,p))
        r = self._accept(self.env.clear(p[0],p[1],int(ch)))
        self.position = p
        self.counters['clear_attempts'] += 1
        self.counters['certified_clear_attempts' if certified else 'heuristic_clear_attempts'] += 1
        success = r['clear_result'] == 'success'
        if success:
            self.cleared.add(ch)
        else:
            self.counters['failed_clear'] += 1
        self.trace.append({'action':'clear','x':p[0],'y':p[1],'channel':ch,
                           'result':r['clear_result'],'certified_before_action':certified,
                           'virtual_time_s':self.virtual_time})
        if certified and not success:
            raise RuntimeError('Certified optical clear failed: observations/environment violate the stated model')
        return success

    def _time_guard(self):
        if self.deadline and time.monotonic() > self.deadline:
            raise TimeoutError('Remaining real-time budget nearly exhausted; completeness not certified')

    def _virtual_fallback(self,ch):
        """Preserve the virtual-time reserve; this is never an exit certificate."""
        if self.virtual_time >= _di_VIRTUAL_SAFE_SWITCH_S:
            self.counters['budget_fallbacks'] += 1
            self.cover_polygon(ch)
            return True
        return False

    def visibility_hypotheses(self, ch):
        """Approximate belief for ordering only; never trims the certified polygon.

        Marginalize a uniform 1000..1500 radius and a mixed omni/half-plane
        antenna prior over deterministic interior position/orientation samples.
        Every input is a recorded enter/measure/clear/exit observation.
        """
        signature = (len(self.observations[ch]), len(self.no_signal_points[ch]))
        cached = self._visibility_cache.get(ch)
        if cached and cached[0] == signature:
            return cached[1]
        poly = self.polygons[ch]
        center = (sum(p[0] for p in poly)/len(poly), sum(p[1] for p in poly)/len(poly))
        samples = [center] + [(0.75*p[0]+0.25*center[0], 0.75*p[1]+0.25*center[1]) for p in poly]
        # Fixed finite quadrature is a planning approximation, not a posterior
        # support certificate; an empty quadrature falls back to neutral scores.
        hypotheses = []
        n_angles = 36
        for s in samples:
            positives = [(p[0]-s[0], p[1]-s[1]) for p, _ in self.observations[ch]]
            negatives = [(p[0]-s[0], p[1]-s[1]) for p in self.no_signal_points[ch]]
            lower = max([1000.0]+[math.hypot(*v) for v in positives])
            if lower >= 1500:
                continue
            for k in range(-1, n_angles):
                normal = None if k == -1 else (math.cos(2*math.pi*k/n_angles), math.sin(2*math.pi*k/n_angles))
                if normal and any(normal[0]*x+normal[1]*y < -1e-8 for x,y in positives):
                    continue
                upper = min([1500.0]+[math.hypot(x,y) for x,y in negatives
                            if normal is None or normal[0]*x+normal[1]*y >= 0])
                if upper > lower:
                    prior = .5 if normal is None else .5/n_angles
                    hypotheses.append((s, normal, lower, upper, prior*(upper-lower)))
        self._visibility_cache[ch] = (signature, hypotheses)
        return hypotheses

    def predicted_visibility(self, ch, q):
        hypotheses = self.visibility_hypotheses(ch)
        total = sum(h[4] for h in hypotheses)
        if total <= 0:
            return .5
        hit = 0.0
        for s, normal, lower, upper, weight in hypotheses:
            x,y = q[0]-s[0], q[1]-s[1]
            if normal is not None and normal[0]*x+normal[1]*y < 0:
                continue
            distance = math.hypot(x,y)
            hit += weight*max(0.0,min(1.0,(upper-max(lower,distance))/(upper-lower)))
        return hit/total

    def second_point(self,ch):
        p, deg = self.observations[ch][-1]
        theta = math.radians(deg)
        ux,uy = math.cos(theta),math.sin(theta)
        center,radius = _di_enclosing_circle(self.polygons[ch])
        length = max(0,(center[0]-p[0])*ux+(center[1]-p[1])*uy)
        # The candidate moves mostly toward the source, adding enough lateral
        # baseline to resolve range while avoiding a long out-and-back detour.
        advance = max(30, length * self.config.get('advance_fraction',0.78))
        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.20)))
        candidates = [(p[0]+advance*ux+sign*lateral*(-uy),
                       p[1]+advance*uy+sign*lateral*ux) for sign in [-1,1]]
        # Favor candidate nearer the other planned search stations, a cheap
        # approximation to downstream route cost, with deterministic tie-break.
        return min(candidates,key=lambda q: (_di_dist(q,self.position) + 0.12*min(_di_dist(q,w) for w in self.points)
            + (self.config.get('visibility_penalty_m',600.0)*(1-self.predicted_visibility(ch,q))
               if self.mode == 4 and self.config.get('visibility_side',True) else 0),q))

    def localize(self,ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations',9))
        for k in range(max_iter):
            if self._virtual_fallback(ch):
                return
            center,radius = _di_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius',100.0) or k >= 3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=_di_dist(self.position,center)
                    margin=max(0,20-radius-1e-6)
                    if distance<=margin:
                        clear_point=self.position
                    elif distance>0:
                        clear_point=(center[0]+margin*(self.position[0]-center[0])/distance,
                                     center[1]+margin*(self.position[1]-center[1])/distance)
                if self.clear(clear_point,ch,certified=radius<=20):
                    return
                if self._virtual_fallback(ch):
                    return
                # A measurement at a failed optical attempt adds no movement.
                kind = self.measure(center,ch)
                if ch in self.cleared:
                    return
                if self._virtual_fallback(ch):
                    return
                if kind == 'direction':
                    continue
                if self.rescue_bearing(ch,k):
                    if ch in self.cleared:
                        return
                    continue
                if self._virtual_fallback(ch):
                    return
            if len(self.observations[ch]) == 1:
                q = self.second_point(ch)
            else:
                # At this distance ±1 degree amounts to only a few metres;
                # moving toward the feasible-set center quickly shrinks it.
                p,deg = self.observations[ch][-1]
                dd = _di_dist(p,center)
                if dd < 25:
                    theta = math.radians(deg)+math.pi/2
                    q = (p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:
                    q = center
            # Do not average the same-location, fixed environmental error.
            if any(_di_dist(q,p)<1e-5 for p,d in self.observations[ch]):
                q = (q[0]+23.0,q[1]+17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q,ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                # Optical clearing is independent of antenna direction.
                center,radius = _di_enclosing_circle(self.polygons[ch])
                if (len(self.observations[ch])>=2 or radius<=100 or
                        self.config.get('rescue_initial_clear',False)):
                    if self.clear(center,ch):
                        return
                    if self._virtual_fallback(ch):
                        return
                self.rescue_bearing(ch,k)
                if ch in self.cleared:
                    return
        self.cover_polygon(ch)

    def rescue_bearing(self,ch,iteration=0):
        """Recover a bearing near a previously visible point after RF loss.

        A full ring is explored if necessary.  This is a speed heuristic;
        completeness comes from the finite optical polygon cover, not an
        assumption that a directional source remains visible after movement.
        """
        if self.mode == 4 and self.config.get('optical_switch',True):
            _, radius = _di_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('optical_radius',300.0):
                self.counters['optical_switches'] = self.counters.get('optical_switches',0)+1
                self.cover_polygon(ch)
                return True
        p,deg=min(self.observations[ch],key=lambda z:_di_dist(z[0],self.position))
        # A half-disk is convex. Along a segment from a known visible point
        # toward a missed point, visibility is an initial interval. Bounded
        # subdivision may recover a nearby bearing; original rescue stays.
        attempts = int(self.config.get('segment_recovery_steps',2)) if self.mode == 4 else 0
        if attempts and self.no_signal_points[ch]:
            missed = self.no_signal_points[ch][-1]
            mirror_strategy = self.config.get('mirror_strategy','expected')
            if mirror_strategy != 'none':
                theta = math.radians(deg)
                normal = (-math.sin(theta),math.cos(theta))
                offset = (missed[0]-p[0])*normal[0]+(missed[1]-p[1])*normal[1]
                mirror = (missed[0]-2*offset*normal[0],missed[1]-2*offset*normal[1])
                middle = ((p[0]+missed[0])/2,(p[1]+missed[1])/2)
                allowed = abs(offset)>=5 and math.hypot(*mirror)<=3500
                allowed = allowed and not any(_di_dist(mirror,q)<1e-6 for q in self.no_signal_points[ch]+[o[0] for o in self.observations[ch]])
                if allowed and mirror_strategy != 'always':
                    cost = lambda q:(_di_dist(self.position,q)/5+5)/max(.05,self.predicted_visibility(ch,q))
                    factor = 2 if mirror_strategy == 'strict' else 1
                    allowed = factor*cost(mirror)<cost(middle)
                if allowed and self.virtual_time < _di_VIRTUAL_SAFE_SWITCH_S:
                    self.counters['mirror_recovery_measures'] = self.counters.get('mirror_recovery_measures',0)+1
                    kind = self.measure(mirror,ch)
                    if kind in ('direction','near'):
                        return True
                    missed = mirror
            fraction = self.config.get('segment_fraction',.5)
            for _ in range(attempts):
                if self.virtual_time >= _di_VIRTUAL_SAFE_SWITCH_S:
                    return False
                q = ((1-fraction)*p[0]+fraction*missed[0],(1-fraction)*p[1]+fraction*missed[1])
                if any(_di_dist(q,old)<1e-6 for old,d in self.observations[ch]):
                    break
                self.counters['segment_recovery_measures'] = self.counters.get('segment_recovery_measures',0)+1
                kind = self.measure(q,ch)
                if kind in ('direction','near'):
                    return True
                missed = q
        angle=math.radians(deg)
        rr=80.0+iteration*11.0
        angles=[70,-70,110,-110,35,-35,0,180,145,-145,20,-20,90,-90,160,-160]
        if self.mode == 4 and self.config.get('visibility_rescue',True):
            def recovery_cost(offset):
                a = angle+math.radians(offset)
                q = (p[0]+rr*math.cos(a),p[1]+rr*math.sin(a))
                return (_di_dist(self.position,q)/5+5)/max(.05,self.predicted_visibility(ch,q))
            angles.sort(key=recovery_cost)
        for offset in angles:
            if self.virtual_time >= _di_VIRTUAL_SAFE_SWITCH_S:
                return False
            a=angle+math.radians(offset)
            q=(p[0]+rr*math.cos(a),p[1]+rr*math.sin(a))
            if any(_di_dist(q,old)<1e-6 for old,d in self.observations[ch]):
                continue
            kind=self.measure(q,ch)
            if kind in ('direction','near'):
                return True
        return False

    def optical_points(self,ch):
        """Conservative 25m lattice cover, shared by cost selection and fallback."""
        poly = self.polygons[ch]
        # Rotate coordinates along the first bearing, making the narrow wedge
        # bounding rectangle far smaller than its axis-aligned rectangle.
        origin,deg=self.observations[ch][0]
        angle=math.radians(deg)
        u=(math.cos(angle),math.sin(angle)); v=(-u[1],u[0])
        local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
                (p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in poly]
        spacing=25.0
        lo=[math.floor((min(p[d] for p in local)-spacing/2)/spacing) for d in [0,1]]
        hi=[math.ceil((max(p[d] for p in local)+spacing/2)/spacing) for d in [0,1]]
        candidates=[]
        for i in range(lo[0],hi[0]+1):
            row=range(lo[1],hi[1]+1) if i%2==0 else range(hi[1],lo[1]-1,-1)
            for j in row:
                test=local
                for a,b,c in [(1,0,(i+.5)*spacing),(-1,0,(-i+.5)*spacing),
                              (0,1,(j+.5)*spacing),(0,-1,(-j+.5)*spacing)]:
                    test=_di_clip(test,a,b,c)
                if test:
                    candidates.append((origin[0]+i*spacing*u[0]+j*spacing*v[0],
                                       origin[1]+i*spacing*u[1]+j*spacing*v[1]))
        return candidates

    def optical_route(self, ch, points):
        """A complete center-out snake with at most twice the old internal length.

        Probability estimates choose between two complete routes, never remove
        cells. Above the common budget switch retain the original snake.
        """
        if not points:
            return points
        if _di_dist(self.position,points[-1]) < _di_dist(self.position,points[0]):
            points = list(reversed(points))
        order = self.config.get('optical_order','belief')
        _, radius = _di_enclosing_circle(self.polygons[ch])
        if order == 'snake' or radius > 300 or self.virtual_time >= _di_VIRTUAL_SAFE_SWITCH_S:
            return points
        k = min(range(len(points)),key=lambda i:_di_dist(self.position,points[i]))
        routes = [points[k:]+list(reversed(points[:k])),list(reversed(points[:k+1]))+points[k+1:]]
        if order == 'nearest':
            return min(routes,key=lambda route:sum(_di_dist(a,b) for a,b in zip([self.position]+route[:2],route[:3])))
        weights = {}
        for source, normal, lo, hi, weight in self.visibility_hypotheses(ch):
            weights[source] = weights.get(source,0)+weight
        if not weights:
            weights = {p:1.0 for p in self.polygons[ch]}
        def expected_time(route):
            remaining = dict(weights)
            value = 0.0
            previous = self.position
            for point in route:
                cost = _di_dist(previous,point)/5+3
                value += cost*sum(remaining.values())
                remaining = {p:w for p,w in remaining.items() if _di_dist(p,point)>20}
                previous = point
            return value
        return min(routes,key=expected_time)

    def cover_polygon(self,ch):
        """Finite optical cover of the retained polygon; independent of RF direction.

        Every point belongs to a 25 m square centered on this lattice, and is
        at most 25/sqrt(2)<20 m from its center.  Include each cell whose
        bounding box intersects the polygon.  This fallback is conservative.
        """
        self.counters['fallbacks'] += 1
        candidates = self.optical_points(ch)
        if self.mode == 4:
            candidates = self.optical_route(ch,candidates)
        # The complete column snake is retained (or visited center-out).
        # Convexity makes occupied columns
        # consecutive.  At most 62 columns x 3 rows are possible, and every
        # original snake inter-column step is <=25*sqrt(5). A center-out
        # route may jump between columns, but its total length is <=2L.
        for point in candidates:
            if self.clear(point,ch):
                return
        raise RuntimeError('Finite optical covering exhausted without success: model mismatch')

    def scan_station(self,index,defer=False):
        p=self.points[index]
        unknown=[c for c in range(1,21) if c not in self.cleared and not self.observations[c]]
        if self.channel in unknown:
            unknown.remove(self.channel); unknown.insert(0,self.channel)
        self.counters['scan_stations'] += 1
        for ch in unknown:
            self.measure(p,ch)
            self.scanned[ch].add(index)
        pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
        if defer:
            for ch in pending:
                if any(_di_dist(p,old)<1e-5 for old,d in self.observations[ch]):
                    continue
                center,radius=_di_enclosing_circle(self.polygons[ch])
                if _di_dist(center,p)<=1500+radius:
                    self.measure(p,ch)
            return
        while pending:
            ch=min(pending,key=lambda c:_di_dist(self.position,_di_enclosing_circle(self.polygons[c])[0]))
            self.localize(ch)
            pending.remove(ch)

    def next_station(self,todo):
        if not self.config.get('route_optimization',True) or len(todo)<3:
            return min(todo,key=lambda i:_di_dist(self.position,self.points[i]))
        remaining=set(todo); greedy=[]; p=self.position
        while remaining:
            i=min(remaining,key=lambda i:_di_dist(p,self.points[i]))
            greedy.append(i); remaining.remove(i); p=self.points[i]
        def length(route):
            return _di_dist(self.position,self.points[route[0]])+sum(
                _di_dist(self.points[a],self.points[b]) for a,b in zip(route,route[1:]))
        def improve(route):
            route=route[:]
            for iteration in range(60):
                change=0; best=None
                for i in range(len(route)-1):
                    before=self.position if i==0 else self.points[route[i-1]]
                    for j in range(i+1,len(route)):
                        a,b=self.points[route[i]],self.points[route[j]]
                        delta=_di_dist(before,b)-_di_dist(before,a)
                        if j+1<len(route):
                            after=self.points[route[j+1]]
                            delta+=_di_dist(a,after)-_di_dist(b,after)
                        if delta<change-1e-7:
                            change,best=delta,(i,j)
                if best is None:
                    break
                i,j=best; route[i:j+1]=reversed(route[i:j+1])
            return route
        candidates=[improve(greedy),improve(sorted(todo)),improve(sorted(todo,reverse=True))]
        return min(candidates,key=length)[0]

    def run(self):
        started=time.monotonic()
        entered=self._accept(self.env.enter())
        remaining=float(entered.get('remaining_real_duration_s',1200))
        self.deadline=started+max(0,remaining-5)
        todo=set(range(len(self.points)))
        visited=[]
        while todo or any(self.observations[c] and c not in self.cleared for c in range(1,21)):
            if self.config.get('joint_scheduling',False):
                pending=[c for c in range(1,21) if self.observations[c] and c not in self.cleared]
                index=self.next_station(todo) if todo else None
                if pending:
                    ch=min(pending,key=lambda c:_di_dist(self.position,_di_enclosing_circle(self.polygons[c])[0]))
                    target=_di_enclosing_circle(self.polygons[ch])[0]
                    source_cost=_di_dist(self.position,target)*self.config.get('source_priority',1.0)
                    station_cost=(_di_dist(self.position,self.points[index]) if index is not None else float('inf'))
                    if source_cost<=station_cost:
                        self.localize(ch)
                        if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                            break
                        continue
                self.scan_station(index,defer=True)
                visited.append(index);todo.remove(index)
                if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                    break
                continue
            index=self.next_station(todo)
            self.scan_station(index)
            visited.append(index); todo.remove(index)
            if self.config.get('upper_bound_stop',True) and len(self.cleared)>=16:
                break
        unresolved=[c for c in range(1,21) if c not in self.cleared]
        count_certificate=len(self.cleared)>=16
        geometric_certificate=all(not self.observations[c] and len(self.scanned[c])==len(self.points)
                                  for c in unresolved)
        certificate=count_certificate or geometric_certificate
        if not certificate:
            raise RuntimeError('Search ended without complete coverage certificate')
        final=self._accept(self.env.exit())
        return {'mode':self.mode,'cleared_count':len(self.cleared),'cleared_channels':sorted(self.cleared),
                'virtual_time_s':self.virtual_time,'average_time_s':self.virtual_time/max(1,len(self.cleared)),
                'program_time_s':time.monotonic()-started,'coverage_complete':certificate,
                'completion_certified':certificate,'geometric_coverage_complete':geometric_certificate,
                'coverage_point_count':len(self.points),'visited_points':visited,
                'certificate_type':'known_count_upper_bound' if count_certificate else 'complete_geometric_coverage',
                'unresolved_channels_certified_absent':unresolved,'counters':dict(self.counters),
                'exit_response':final}


class _OpportunitySensing:
    """Reuses arrival points; hypothetical beliefs only determine paid actions."""
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self._active_target = None
        self._sharing = False
        self._sharing_spent_s = 0.0

    def measure(self, p, ch):
        kind = super().measure(p, ch)
        if self._active_target is not None and not self._sharing:
            self.share_observations(self._active_target)
        return kind

    def localize(self, ch):
        self._active_target = ch
        try:
            super().localize(ch)
        finally:
            self._active_target = None
        self.share_observations(ch)

    def share_observations(self, exclude=None):
        style = self.config.get('sharing_style','naive')
        if style == 'off' or self._sharing:
            return
        self._sharing = True
        try:
            p = self.position
            for ch in range(1,21):
                # Each supplemental measure costs <=6 s, or <=11 s with near
                # immediately cleared. Hard cap makes the bound compositional.
                if self.virtual_time >= 180000 or self._sharing_spent_s >= 6000:
                    break
                if ch == exclude or ch in self.cleared or not self.observations[ch]:
                    continue
                if min(_sp_dist(p,old) for old,_ in self.observations[ch]) < 60:
                    continue
                poly = self.polygons[ch]
                center,radius = _sp_enclosing_circle(poly)
                if radius <= 20 or _sp_dist(center,p) > 1500+radius:
                    continue
                targets = [center]
                if style == 'quadrature':
                    # Spread hypotheses over the retained region; unlike a
                    # point estimate, these never enter the actual polygon.
                    far = max(poly,key=lambda q:_sp_dist(q,center))
                    other = max(poly,key=lambda q:_sp_dist(q,far))
                    targets += [(.25*center[0]+.75*q[0],.25*center[1]+.75*q[1]) for q in (far,other)]
                gains=[]
                for target in targets:
                    bearing=math.degrees(math.atan2(target[1]-p[1],target[0]-p[0]))
                    predicted=_sp_add_bearing(poly,p,bearing)
                    gains.append(max(0.,radius-_sp_enclosing_circle(predicted)[1]) if predicted else 0.)
                gain=sum(gains)/len(gains)
                if style in ('visibility','quadrature') and self.mode == 4:
                    gain *= self.predicted_visibility(ch,p)
                threshold=self.config.get('sharing_gain_m',30.)
                if gain < threshold:
                    continue
                before=self.virtual_time
                self.counters['opportunity_measures']=self.counters.get('opportunity_measures',0)+1
                self.measure(p,ch)
                self._sharing_spent_s += self.virtual_time-before
        finally:
            self._sharing = False

class _SharedSpatial(_OpportunitySensing, _sp_Solver):
    pass

class _SharedDirectional(_OpportunitySensing, _di_Solver):
    pass



def _geo_convex_hull(points):
    points=sorted(set(points))
    if len(points)<=2:
        return points
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:
            upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]

def _geo_outside_disk_hull(poly,origin,radius=1000.0-1e-6):
    """Convex outer hull of polygon outside a known no-signal disk.

    Extreme points lie on old polygon edges: keep exterior vertices and each
    edge/circle intersection. Taking their convex hull is conservative even
    when the actual remaining feasible region is disconnected or nonconvex.
    """
    points=[p for p in poly if _geo_dist(p,origin)>=radius-1e-8]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1];xx,yy=a[0]-origin[0],a[1]-origin[1]
        aa=dx*dx+dy*dy
        if aa<1e-20:
            continue
        bb=2*(xx*dx+yy*dy);cc=xx*xx+yy*yy-radius*radius
        discriminant=bb*bb-4*aa*cc
        if discriminant<0:
            continue
        square=math.sqrt(discriminant)
        for t in ((-bb-square)/(2*aa),(-bb+square)/(2*aa)):
            if -1e-10<=t<=1+1e-10:
                t=max(0.,min(1.,t));points.append((a[0]+t*dx,a[1]+t*dy))
    return _geo_convex_hull(points)

def _geo_add_bearing(poly, p, deg, tighten=True):
    lo, hi = math.radians(deg) - _geo_EPS, math.radians(deg) + _geo_EPS
    # cross(u_lo, target-p)>=0; cross(u_hi, target-p)<=0.
    for a, b in [(math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))]:
        poly = _geo_clip(poly, a, b, a * p[0] + b * p[1])
    # Effective receive radius is at most 1500; tangent half-planes preserve it.
    for i in range(24):
        a, b = math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24)
        poly = _geo_clip(poly, a, b, 1500 + a * p[0] + b * p[1])
    # Refine only with valid tangent half-planes from known physical bounds.
    # This consumes no sensing time and remains an outer approximation.
    for _ in range(3):
        if not tighten or len(poly)>=48:
            break
        for origin,limit in ((p,1500.0),((0.0,0.0),1800.0)):
            for q in poly[:]:
                if len(poly)>=48:
                    break
                dx,dy=q[0]-origin[0],q[1]-origin[1]
                length=math.hypot(dx,dy)
                if length>limit+1e-8:
                    a,b=dx/length,dy/length
                    poly=_geo_clip(poly,a,b,limit+a*origin[0]+b*origin[1])
    return poly

# R2_open R1: bounded set refinement inside S0 Q3 opportunity sensing.
# Only actual interface observations affect the certified location polygon.
_geo_dist = _sp_dist
_geo_clip = _sp_clip
_geo_EPS = _sp_EPS


class _GeometrySpatial(_SharedSpatial):
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self.failed_clear_points = {c: [] for c in range(1, 21)}

    def _exclude_observed_disks(self, ch):
        if ch not in self.polygons:
            return
        poly = self.polygons[ch]
        disks = []
        if self.config.get('geom_no_signal', False):
            disks += [(p, 1000.0 - 1e-6) for p in self.no_signal_points[ch]]
        if self.config.get('geom_failure', False):
            disks += [(p, 20.0 - 1e-6) for p in self.failed_clear_points[ch]]
        for p, radius in disks:
            if len(poly) > 96:
                self.counters['geometry_budget_skips'] = self.counters.get('geometry_budget_skips', 0) + 1
                break
            refined = _geo_outside_disk_hull(poly, p, radius)
            if not refined:
                raise RuntimeError('Observed exclusion contradicts bounded bearing constraints')
            # Discarding a computationally large refinement is conservative.
            if len(refined) <= 96:
                poly = refined
        self.polygons[ch] = poly

    def measure(self, p, ch):
        # Update geometry BEFORE invoking opportunity sensing. Calling the
        # shared parent's wrapper first would score with a stale target set.
        kind = _sp_Solver.measure(self, p, ch)
        if kind == 'direction' and self.config.get('geom_tangent', False):
            self.polygons[ch] = _geo_add_bearing(self.polygons[ch], p, self.observations[ch][-1][1])
            if not self.polygons[ch]:
                raise RuntimeError('Physical tangent constraints removed all feasible points')
        if kind in ('direction', 'no_signal'):
            self._exclude_observed_disks(ch)
        if self._active_target is not None and not self._sharing:
            self.share_observations(self._active_target)
        return kind

    def clear(self, p, ch, certified=False):
        success = super().clear(p, ch, certified=certified)
        if not success:
            self.failed_clear_points[ch].append(tuple(p))
            self._exclude_observed_disks(ch)
        return success


# R2: A2 action-cost second point plus same-location certified clear.
class _ActionSpatial(_GeometrySpatial):
    def __init__(self, env, mode=3, **config):
        super().__init__(env, mode=mode, **config)
        self._servicing = False

    def _parent_second_point(self, ch):
        return super().second_point(ch)

    def _serve_certified_here(self, exclude=None):
        if self._servicing or not self.config.get('same_location_clear',False):
            return
        self._servicing = True
        try:
            p=self.position
            for other in range(1,21):
                if other==exclude or other in self.cleared or other not in self.polygons:
                    continue
                # A norm is convex; checking vertices certifies the whole hull.
                if all(_sp_dist(p,v)<=20.0-1e-6 for v in self.polygons[other]):
                    self.counters['same_location_clears']=self.counters.get('same_location_clears',0)+1
                    self.clear(p,other,certified=True)
        finally:
            self._servicing=False

    def measure(self,p,ch):
        result=super().measure(p,ch)
        self._serve_certified_here(ch)
        return result

    def clear(self,p,ch,certified=False):
        success=super().clear(p,ch,certified=certified)
        if success:
            self._serve_certified_here(ch)
        return success

    def belief_quadrature(self,poly,count=9):
        """Deterministic area-uniform quadrature, used only to rank actions.

        Samples are hypotheses inside the bounded-error polygon, never true
        source coordinates. They do not participate in correctness certificates.
        """
        center=(sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
        triangles=[];total=0.0
        for a,b in zip(poly,poly[1:]+poly[:1]):
            area=abs((a[0]-center[0])*(b[1]-center[1])-(a[1]-center[1])*(b[0]-center[0]))/2
            if area>1e-12:
                total+=area;triangles.append((total,a,b))
        if not triangles:
            return [center]
        samples=[]
        for k in range(count):
            area=total*(k+.5)/count
            _,a,b=next(t for t in triangles if t[0]>=area)
            # Irrational rotations decorrelate radial and angular coordinates.
            rr=math.sqrt(((k+.5)*0.618033988749895)%1)
            v=((k+.5)*0.414213562373095)%1
            samples.append(((1-rr)*center[0]+rr*((1-v)*a[0]+v*b[0]),
                            (1-rr)*center[1]+rr*((1-v)*a[1]+v*b[1])))
        return samples

    def planning_hypotheses(self,ch):
        """Rank with observation-consistent hypotheses, not outer-hull holes.

        Filtering never changes the authoritative polygon or any certificate.
        A finite empty proposal set is a sampling failure, not source absence.
        """
        poly=self.polygons[ch]
        original=self.belief_quadrature(poly)
        def consistent(target):
            if math.hypot(*target)>1800+1e-6:
                return False
            if any(_sp_dist(target,p)>1500+1e-6 for p,_ in self.observations[ch]):
                return False
            if self.mode==3 and any(_sp_dist(target,p)<1000-1e-6 for p in self.no_signal_points[ch]):
                return False
            return True
        if all(consistent(t) for t in original):
            return original
        proposals=[t for t in self.belief_quadrature(poly,81) if consistent(t)]
        if not proposals:
            return original
        n=min(9,len(proposals))
        return [proposals[min(len(proposals)-1,int((i+.5)*len(proposals)/n))] for i in range(n)]

    def predicted_polygon(self,poly,q,deg):
        # The full retained polygon remains authoritative. The two half-plane
        # prediction is only a cheap planning surrogate and never updates it.
        lo,hi=math.radians(deg)-_sp_EPS,math.radians(deg)+_sp_EPS
        for a,b in [(math.sin(lo),-math.cos(lo)),(-math.sin(hi),math.cos(hi))]:
            poly=_sp_clip(poly,a,b,a*q[0]+b*q[1])
        return poly

    def second_point(self,ch):
        if not self.config.get('active_information',self.mode==3):
            return self._parent_second_point(ch)
        poly=self.polygons[ch];p,deg=self.observations[ch][-1]
        center,radius=_sp_enclosing_circle(poly)
        theta=math.radians(deg);u=(math.cos(theta),math.sin(theta));v=(-u[1],u[0])
        length=max(30,(center[0]-p[0])*u[0]+(center[1]-p[1])*u[1])
        candidates=[self._parent_second_point(ch)]
        for advance in (.35,.65,.95):
            for lateral in (45.,100.,175.):
                for sign in (-1,1):
                    candidates.append((p[0]+advance*length*u[0]+sign*lateral*v[0],
                                       p[1]+advance*length*u[1]+sign*lateral*v[1]))
        targets=self.planning_hypotheses(ch)
        def score(q):
            future=0.0
            for target in targets:
                dd=_sp_dist(q,target)
                if dd>1500:
                    future+=_sp_dist(q,p)/5+35+_sp_dist(p,target)/5
                    continue
                observed_cost=0.0
                for error in (-.8,0.,.8):
                    bearing=math.degrees(math.atan2(target[1]-q[1],target[0]-q[0]))+error
                    posterior=self.predicted_polygon(poly,q,bearing)
                    if not posterior:
                        observed_cost+=1000.0/3
                        continue
                    c,r=_sp_enclosing_circle(posterior)
                    # Predict one clear, then the cost of correcting a failed
                    # point estimate. All quantities are virtual seconds.
                    cost=_sp_dist(q,c)/5+5
                    if _sp_dist(c,target)>20:
                        cost+=8+_sp_dist(c,target)/5
                    observed_cost+=cost/3
                if self.mode==4:
                    # Planning prior, not a guarantee: condition unknown receive
                    # radius on the old visible position and conservatively use
                    # an unknown directional half-plane for every source.
                    old_distance=_sp_dist(p,target)
                    low=max(1000.0,old_distance)
                    receive=1.0 if dd<=low else max(0.0,(1500.0-dd)/max(1e-9,1500.0-low))
                    if dd>1e-8 and old_distance>1e-8:
                        cosine=((p[0]-target[0])*(q[0]-target[0])+(p[1]-target[1])*(q[1]-target[1]))/(dd*old_distance)
                        receive*=1-math.acos(max(-1.,min(1.,cosine)))/math.pi
                    loss_cost=_sp_dist(q,p)/5+_sp_dist(p,target)/5+25.0
                    future+=receive*observed_cost+(1-receive)*loss_cost
                else:
                    future+=observed_cost
            return _sp_dist(self.position,q)/5+5+future/len(targets)
        return min(candidates,key=lambda q:(score(q),q))

BASELINE_CONFIG = dict(_sp_BASELINE_CONFIG)
OPTIMIZED_CONFIGS = {
    3: dict(_sp_OPTIMIZED_CONFIGS[3], sharing_style='visibility', sharing_gain_m=60.,
            geom_tangent=True, geom_no_signal=True, geom_failure=True, active_information=False, same_location_clear=True),
    4: dict(_di_OPTIMIZED_CONFIGS[4]),
}


class Solver:
    def __new__(cls, env, mode=3, **config):
        if mode not in (3, 4):
            raise ValueError('mode must be 3 or 4')
        merged = {**OPTIMIZED_CONFIGS[mode], **config}
        parent = _ActionSpatial if mode == 3 else _di_Solver
        return parent(env, mode=mode, **merged)
