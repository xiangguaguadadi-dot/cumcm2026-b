"""B3 R1: new certified 21-station Q4 coverage; C0's Q3 is unchanged.
Self-contained standard-library source. Q3/Q4 namespaces are renamed parent
snapshots, avoiding cross-mode changes to global helpers. No training weights.
"""
"""Black-box, serial source search; no simulator internals are accessed.

Only Python's standard library is required.  The env object supplies four
methods: enter(), measure(x,y,channel), clear(x,y,channel), exit().
"""
import json
import math
import os
import time

q3_EPS = math.radians(1.005001)  # bounded error plus rounding to two decimals
q3_VIRTUAL_SAFE_SWITCH_S = 180000.0  # common to optimized and baseline policies

q3_BASELINE_CONFIG = dict(advance_fraction=.78,lateral_fraction=.20,clear_trial_radius=42,
                       route_optimization=False,upper_bound_stop=False,rescue_initial_clear=True,
                       joint_scheduling=False,clear_standoff=False)
q3_OPTIMIZED_CONFIGS = {
    3: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.55,clear_standoff=True),
    4: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.60,clear_standoff=True),
}


def q3_dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def q3_clip(poly, a, b, c):
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


def q3_initial_polygon():
    # Circumscription, not inscription: the true disk is never cut away.
    radius = 1800 / math.cos(math.pi / 48)
    return [(radius * math.cos(2 * math.pi * i / 48),
             radius * math.sin(2 * math.pi * i / 48)) for i in range(48)]


def q3_add_bearing(poly, p, deg):
    lo, hi = math.radians(deg) - q3_EPS, math.radians(deg) + q3_EPS
    # cross(u_lo, target-p)>=0; cross(u_hi, target-p)<=0.
    for a, b in [(math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))]:
        poly = q3_clip(poly, a, b, a * p[0] + b * p[1])
    # Effective receive radius is at most 1500; tangent half-planes preserve it.
    for i in range(24):
        a, b = math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24)
        poly = q3_clip(poly, a, b, 1500 + a * p[0] + b * p[1])
    return poly


def q3_circle_of_three(a, b, c):
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    dd = 2 * (bx * cy - by * cx)
    if abs(dd) < 1e-10:
        return None
    ub = bx * bx + by * by
    uc = cx * cx + cy * cy
    center = (a[0] + (cy * ub - by * uc) / dd,
              a[1] + (bx * uc - cx * ub) / dd)
    return center, q3_dist(center, a)


def q3_enclosing_circle(poly):
    """Exact finite-vertex minimum enclosing circle, deterministic incremental."""
    if not poly:
        raise RuntimeError('Empty feasible polygon; observations violate the error bound')
    center, radius = poly[0], 0.0
    for i, p in enumerate(poly):
        if q3_dist(center, p) <= radius + 1e-7:
            continue
        center, radius = p, 0.0
        for j in range(i):
            q = poly[j]
            if q3_dist(center, q) <= radius + 1e-7:
                continue
            center = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            radius = q3_dist(p, q) / 2
            for k in range(j):
                r = poly[k]
                if q3_dist(center, r) > radius + 1e-7:
                    candidate = q3_circle_of_three(p, q, r)
                    if candidate is not None:
                        center, radius = candidate
    # Conservative recheck protects the clearing certificate from roundoff.
    return center, max(q3_dist(center, p) for p in poly)


def q3_certified_points(mode):
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


def q3_default_points(mode):
    if mode == 3:
        return q3_certified_points(mode)
    filename=os.path.join(os.path.dirname(__file__),'coverage_points.json')
    if os.path.exists(filename):
        with open(filename,encoding='utf-8') as stream:
            supplied=json.load(stream)
        return [tuple(p) for p in supplied['q'+str(mode)]]
    return q3_certified_points(mode)


class q3_Solver:
    def __init__(self, env, mode=3, **config):
        self.env, self.mode, self.config = env, int(mode), config
        if self.mode not in (3,4):
            raise ValueError('mode must be 3 or 4')
        self.config={**q3_OPTIMIZED_CONFIGS[self.mode],**config}
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
        self.points = config.get('points') or q3_default_points(self.mode)
        self.points = [tuple(map(float,p)) for p in self.points]
        certified=q3_certified_points(self.mode)
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
            self.polygons[ch] = q3_add_bearing(self.polygons.get(ch,q3_initial_polygon()),p,deg)
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
        if self.virtual_time >= q3_VIRTUAL_SAFE_SWITCH_S:
            self.counters['budget_fallbacks'] += 1
            self.cover_polygon(ch)
            return True
        return False

    def second_point(self,ch):
        p, deg = self.observations[ch][-1]
        theta = math.radians(deg)
        ux,uy = math.cos(theta),math.sin(theta)
        center,radius = q3_enclosing_circle(self.polygons[ch])
        length = max(0,(center[0]-p[0])*ux+(center[1]-p[1])*uy)
        # The candidate moves mostly toward the source, adding enough lateral
        # baseline to resolve range while avoiding a long out-and-back detour.
        advance = max(30, length * self.config.get('advance_fraction',0.78))
        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.20)))
        candidates = [(p[0]+advance*ux+sign*lateral*(-uy),
                       p[1]+advance*uy+sign*lateral*ux) for sign in [-1,1]]
        # Favor candidate nearer the other planned search stations, a cheap
        # approximation to downstream route cost, with deterministic tie-break.
        return min(candidates,key=lambda q: (q3_dist(q,self.position) + 0.12*min(q3_dist(q,w) for w in self.points),q))

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
        if q3_dist(start,center)<=margin:
            return start
        def cost(p):return q3_dist(start,p)+q3_dist(p,target)
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
        feasible=[p for p in candidates if q3_dist(p,center)<=margin+1e-8]
        return min(feasible,key=cost) if feasible else original

    def localize(self,ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations',9))
        for k in range(max_iter):
            if self._virtual_fallback(ch):
                return
            center,radius = q3_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius',100.0) or k >= 3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=q3_dist(self.position,center)
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
                dd = q3_dist(p,center)
                if dd < 25:
                    theta = math.radians(deg)+math.pi/2
                    q = (p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:
                    q = center
            # Do not average the same-location, fixed environmental error.
            if any(q3_dist(q,p)<1e-5 for p,d in self.observations[ch]):
                q = (q[0]+23.0,q[1]+17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q,ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                # Optical clearing is independent of antenna direction.
                center,radius = q3_enclosing_circle(self.polygons[ch])
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
        p,deg=min(self.observations[ch],key=lambda z:q3_dist(z[0],self.position))
        angle=math.radians(deg)
        rr=80.0+iteration*11.0
        angles=[70,-70,110,-110,35,-35,0,180,145,-145,20,-20,90,-90,160,-160]
        for offset in angles:
            if self.virtual_time >= q3_VIRTUAL_SAFE_SWITCH_S:
                return False
            a=angle+math.radians(offset)
            q=(p[0]+rr*math.cos(a),p[1]+rr*math.sin(a))
            if any(q3_dist(q,old)<1e-6 for old,d in self.observations[ch]):
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
                    test=q3_clip(test,a,b,c)
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
                if any(q3_dist(p,old)<1e-5 for old,d in self.observations[ch]):
                    continue
                center,radius=q3_enclosing_circle(self.polygons[ch])
                if q3_dist(center,p)<=1500+radius:
                    self.measure(p,ch)
            return
        while pending:
            ch=min(pending,key=lambda c:q3_dist(self.position,q3_enclosing_circle(self.polygons[c])[0]))
            self.localize(ch)
            pending.remove(ch)

    def next_station(self,todo):
        if not self.config.get('route_optimization',True) or len(todo)<3:
            return min(todo,key=lambda i:q3_dist(self.position,self.points[i]))
        remaining=set(todo); greedy=[]; p=self.position
        while remaining:
            i=min(remaining,key=lambda i:q3_dist(p,self.points[i]))
            greedy.append(i); remaining.remove(i); p=self.points[i]
        def length(route):
            return q3_dist(self.position,self.points[route[0]])+sum(
                q3_dist(self.points[a],self.points[b]) for a,b in zip(route,route[1:]))
        def improve(route):
            route=route[:]
            for iteration in range(60):
                change=0; best=None
                for i in range(len(route)-1):
                    before=self.position if i==0 else self.points[route[i-1]]
                    for j in range(i+1,len(route)):
                        a,b=self.points[route[i]],self.points[route[j]]
                        delta=q3_dist(before,b)-q3_dist(before,a)
                        if j+1<len(route):
                            after=self.points[route[j+1]]
                            delta+=q3_dist(a,after)-q3_dist(b,after)
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
            self.points[k] if kind=='station' else q3_enclosing_circle(self.polygons[k])[0]
            for kind,k in tasks]
        n=len(tasks)
        ds=[[q3_dist(a,b) for b in positions] for a in positions]
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
                q3_enclosing_circle(self.polygons[c])[1] <=
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
                    ch=min(pending,key=lambda c:q3_dist(self.position,q3_enclosing_circle(self.polygons[c])[0]))
                    target=q3_enclosing_circle(self.polygons[ch])[0]
                    source_cost=q3_dist(self.position,target)*self.config.get('source_priority',1.0)
                    station_cost=(q3_dist(self.position,self.points[index]) if index is not None else float('inf'))
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

q4_EPS = math.radians(1.005001)  # bounded error plus rounding to two decimals
q4_VIRTUAL_SAFE_SWITCH_S = 180000.0  # common to optimized and baseline policies

q4_BASELINE_CONFIG = dict(advance_fraction=.78,lateral_fraction=.20,clear_trial_radius=42,
                       route_optimization=False,upper_bound_stop=False,rescue_initial_clear=True,
                       joint_scheduling=False,clear_standoff=False)
q4_OPTIMIZED_CONFIGS = {
    3: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.55,clear_standoff=True),
    4: dict(advance_fraction=.60,lateral_fraction=.15,clear_trial_radius=100,
            route_optimization=True,upper_bound_stop=True,rescue_initial_clear=False,
            joint_scheduling=True,source_priority=1.60,clear_standoff=True),
}


def q4_dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def q4_clip(poly, a, b, c):
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


def q4_initial_polygon():
    # Circumscription, not inscription: the true disk is never cut away.
    radius = 1800 / math.cos(math.pi / 48)
    return [(radius * math.cos(2 * math.pi * i / 48),
             radius * math.sin(2 * math.pi * i / 48)) for i in range(48)]


def q4_add_bearing(poly, p, deg):
    lo, hi = math.radians(deg) - q4_EPS, math.radians(deg) + q4_EPS
    # cross(u_lo, target-p)>=0; cross(u_hi, target-p)<=0.
    for a, b in [(math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))]:
        poly = q4_clip(poly, a, b, a * p[0] + b * p[1])
    # Effective receive radius is at most 1500; tangent half-planes preserve it.
    for i in range(24):
        a, b = math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24)
        poly = q4_clip(poly, a, b, 1500 + a * p[0] + b * p[1])
    return poly


def q4_circle_of_three(a, b, c):
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    dd = 2 * (bx * cy - by * cx)
    if abs(dd) < 1e-10:
        return None
    ub = bx * bx + by * by
    uc = cx * cx + cy * cy
    center = (a[0] + (cy * ub - by * uc) / dd,
              a[1] + (bx * uc - cx * ub) / dd)
    return center, q4_dist(center, a)


def q4_enclosing_circle(poly):
    """Exact finite-vertex minimum enclosing circle, deterministic incremental."""
    if not poly:
        raise RuntimeError('Empty feasible polygon; observations violate the error bound')
    center, radius = poly[0], 0.0
    for i, p in enumerate(poly):
        if q4_dist(center, p) <= radius + 1e-7:
            continue
        center, radius = p, 0.0
        for j in range(i):
            q = poly[j]
            if q4_dist(center, q) <= radius + 1e-7:
                continue
            center = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            radius = q4_dist(p, q) / 2
            for k in range(j):
                r = poly[k]
                if q4_dist(center, r) > radius + 1e-7:
                    candidate = q4_circle_of_three(p, q, r)
                    if candidate is not None:
                        center, radius = candidate
    # Conservative recheck protects the clearing certificate from roundoff.
    return center, max(q4_dist(center, p) for p in poly)


def q4_certified_points(mode):
    """Analytic source of the certificate, independent of external JSON data."""
    if mode == 3:
        rr = 1800 * math.cos(math.pi / 6)
        return [(0.0, 0.0)] + [(rr * math.cos(i * math.pi / 3), rr * math.sin(i * math.pi / 3)) for i in range(6)]
    # B3: exact-decimal 21-station continuous half-plane coverage certificate.
    # Each certified quadtree leaf lies in the convex hull of stations all
    # within 1000m of the entire leaf; at least one is in every closed
    # emission half-plane. See research/certificate_21_999_1864.json.
    return [[0.0, 0.0], [999.0, 0.0], [706.399674, 706.399674], [0.0, 999.0], [-706.399674, 706.399674], [-999.0, 0.0], [-706.399674, -706.399674], [-0.0, -999.0], [706.399674, -706.399674], [1864.0, 0.0], [1614.271353, 932.0], [932.0, 1614.271353], [0.0, 1864.0], [-932.0, 1614.271353], [-1614.271353, 932.0], [-1864.0, 0.0], [-1614.271353, -932.0], [-932.0, -1614.271353], [-0.0, -1864.0], [932.0, -1614.271353], [1614.271353, -932.0]]


def q4_default_points(mode):
    filename=os.path.join(os.path.dirname(__file__),'coverage_points.json')
    if os.path.exists(filename):
        with open(filename,encoding='utf-8') as stream:
            supplied=json.load(stream)
        return [tuple(p) for p in supplied['q'+str(mode)]]
    return q4_certified_points(mode)


class q4_Solver:
    def __init__(self, env, mode=3, **config):
        self.env, self.mode, self.config = env, int(mode), config
        if self.mode not in (3,4):
            raise ValueError('mode must be 3 or 4')
        self.config={**q4_OPTIMIZED_CONFIGS[self.mode],**config}
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
        self.points = config.get('points') or q4_default_points(self.mode)
        self.points = [tuple(map(float,p)) for p in self.points]
        certified=q4_certified_points(self.mode)
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
            self.polygons[ch] = q4_add_bearing(self.polygons.get(ch,q4_initial_polygon()),p,deg)
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
        if self.virtual_time >= q4_VIRTUAL_SAFE_SWITCH_S:
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
        center,radius = q4_enclosing_circle(self.polygons[ch])
        length = max(0,(center[0]-p[0])*ux+(center[1]-p[1])*uy)
        # The candidate moves mostly toward the source, adding enough lateral
        # baseline to resolve range while avoiding a long out-and-back detour.
        advance = max(30, length * self.config.get('advance_fraction',0.78))
        lateral = max(45,min(190,length*self.config.get('lateral_fraction',0.20)))
        candidates = [(p[0]+advance*ux+sign*lateral*(-uy),
                       p[1]+advance*uy+sign*lateral*ux) for sign in [-1,1]]
        # Favor candidate nearer the other planned search stations, a cheap
        # approximation to downstream route cost, with deterministic tie-break.
        return min(candidates,key=lambda q: (q4_dist(q,self.position) + 0.12*min(q4_dist(q,w) for w in self.points)
            + (self.config.get('visibility_penalty_m',600.0)*(1-self.predicted_visibility(ch,q))
               if self.mode == 4 and self.config.get('visibility_side',True) else 0),q))

    def localize(self,ch):
        if ch in self.cleared:
            return
        max_iter = int(self.config.get('localization_iterations',9))
        for k in range(max_iter):
            if self._virtual_fallback(ch):
                return
            center,radius = q4_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('clear_trial_radius',100.0) or k >= 3:
                clear_point=center
                if radius<=20 and self.config.get('clear_standoff',True):
                    distance=q4_dist(self.position,center)
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
                dd = q4_dist(p,center)
                if dd < 25:
                    theta = math.radians(deg)+math.pi/2
                    q = (p[0]+35*math.cos(theta),p[1]+35*math.sin(theta))
                else:
                    q = center
            # Do not average the same-location, fixed environmental error.
            if any(q4_dist(q,p)<1e-5 for p,d in self.observations[ch]):
                q = (q[0]+23.0,q[1]+17.0)
            self.counters['localization_moves'] += 1
            kind = self.measure(q,ch)
            if ch in self.cleared:
                return
            if self._virtual_fallback(ch):
                return
            if kind == 'no_signal':
                # Optical clearing is independent of antenna direction.
                center,radius = q4_enclosing_circle(self.polygons[ch])
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
            _, radius = q4_enclosing_circle(self.polygons[ch])
            if radius <= self.config.get('optical_radius',300.0):
                self.counters['optical_switches'] = self.counters.get('optical_switches',0)+1
                self.cover_polygon(ch)
                return True
        p,deg=min(self.observations[ch],key=lambda z:q4_dist(z[0],self.position))
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
                allowed = allowed and not any(q4_dist(mirror,q)<1e-6 for q in self.no_signal_points[ch]+[o[0] for o in self.observations[ch]])
                if allowed and mirror_strategy != 'always':
                    cost = lambda q:(q4_dist(self.position,q)/5+5)/max(.05,self.predicted_visibility(ch,q))
                    factor = 2 if mirror_strategy == 'strict' else 1
                    allowed = factor*cost(mirror)<cost(middle)
                if allowed and self.virtual_time < q4_VIRTUAL_SAFE_SWITCH_S:
                    self.counters['mirror_recovery_measures'] = self.counters.get('mirror_recovery_measures',0)+1
                    kind = self.measure(mirror,ch)
                    if kind in ('direction','near'):
                        return True
                    missed = mirror
            fraction = self.config.get('segment_fraction',.5)
            for _ in range(attempts):
                if self.virtual_time >= q4_VIRTUAL_SAFE_SWITCH_S:
                    return False
                q = ((1-fraction)*p[0]+fraction*missed[0],(1-fraction)*p[1]+fraction*missed[1])
                if any(q4_dist(q,old)<1e-6 for old,d in self.observations[ch]):
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
                return (q4_dist(self.position,q)/5+5)/max(.05,self.predicted_visibility(ch,q))
            angles.sort(key=recovery_cost)
        for offset in angles:
            if self.virtual_time >= q4_VIRTUAL_SAFE_SWITCH_S:
                return False
            a=angle+math.radians(offset)
            q=(p[0]+rr*math.cos(a),p[1]+rr*math.sin(a))
            if any(q4_dist(q,old)<1e-6 for old,d in self.observations[ch]):
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
                    test=q4_clip(test,a,b,c)
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
        if q4_dist(self.position,points[-1]) < q4_dist(self.position,points[0]):
            points = list(reversed(points))
        order = self.config.get('optical_order','belief')
        _, radius = q4_enclosing_circle(self.polygons[ch])
        if order == 'snake' or radius > 300 or self.virtual_time >= q4_VIRTUAL_SAFE_SWITCH_S:
            return points
        k = min(range(len(points)),key=lambda i:q4_dist(self.position,points[i]))
        routes = [points[k:]+list(reversed(points[:k])),list(reversed(points[:k+1]))+points[k+1:]]
        if order == 'nearest':
            return min(routes,key=lambda route:sum(q4_dist(a,b) for a,b in zip([self.position]+route[:2],route[:3])))
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
                cost = q4_dist(previous,point)/5+3
                value += cost*sum(remaining.values())
                remaining = {p:w for p,w in remaining.items() if q4_dist(p,point)>20}
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
                if any(q4_dist(p,old)<1e-5 for old,d in self.observations[ch]):
                    continue
                center,radius=q4_enclosing_circle(self.polygons[ch])
                if q4_dist(center,p)<=1500+radius:
                    self.measure(p,ch)
            return
        while pending:
            ch=min(pending,key=lambda c:q4_dist(self.position,q4_enclosing_circle(self.polygons[c])[0]))
            self.localize(ch)
            pending.remove(ch)

    def next_station(self,todo):
        if not self.config.get('route_optimization',True) or len(todo)<3:
            return min(todo,key=lambda i:q4_dist(self.position,self.points[i]))
        remaining=set(todo); greedy=[]; p=self.position
        while remaining:
            i=min(remaining,key=lambda i:q4_dist(p,self.points[i]))
            greedy.append(i); remaining.remove(i); p=self.points[i]
        def length(route):
            return q4_dist(self.position,self.points[route[0]])+sum(
                q4_dist(self.points[a],self.points[b]) for a,b in zip(route,route[1:]))
        def improve(route):
            route=route[:]
            for iteration in range(60):
                change=0; best=None
                for i in range(len(route)-1):
                    before=self.position if i==0 else self.points[route[i-1]]
                    for j in range(i+1,len(route)):
                        a,b=self.points[route[i]],self.points[route[j]]
                        delta=q4_dist(before,b)-q4_dist(before,a)
                        if j+1<len(route):
                            after=self.points[route[j+1]]
                            delta+=q4_dist(a,after)-q4_dist(b,after)
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
                    ch=min(pending,key=lambda c:q4_dist(self.position,q4_enclosing_circle(self.polygons[c])[0]))
                    target=q4_enclosing_circle(self.polygons[ch])[0]
                    source_cost=q4_dist(self.position,target)*self.config.get('source_priority',1.0)
                    station_cost=(q4_dist(self.position,self.points[index]) if index is not None else float('inf'))
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

OPTIMIZED_CONFIGS={3:dict(q3_OPTIMIZED_CONFIGS[3]),4:dict(q4_OPTIMIZED_CONFIGS[4])}
BASELINE_CONFIG=dict(q3_BASELINE_CONFIG)
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        parent=q3_Solver if mode==3 else q4_Solver
        return parent(env,mode=mode,**config)
