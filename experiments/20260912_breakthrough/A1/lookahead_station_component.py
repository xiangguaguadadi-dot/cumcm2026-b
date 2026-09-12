"""D3: compare certified incoming and two-leg projection station proposals."""
_A1_LOOKAHEAD_STATION_PARENT=Solver

class A1LookaheadStationSpatial(A1RotatedMinimaxSpatial):
    def spatial_next_task(self,todo):
        task=super().spatial_next_task(todo)
        if not task or task[0]!='station' or task[1]==0 or self.virtual_time>=180000.:
            return task
        index=task[1];p=self.position;old=self.points[index]
        distance=math.dist(p,old)
        if distance<2.:
            return task
        assert index in todo
        assert all(index not in self.scanned[ch] for ch in range(1,21)
                   if not self.observations[ch] and ch not in self.cleared)
        start=time.perf_counter()
        original=self.points[:]
        safe,base_radius,base_vertices=a1_cover_certificate(original)
        self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
        if not safe:
            self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
            return task
        target=getattr(self,'route_successor',None)
        route_cost=lambda q:math.dist(p,q)+(math.dist(q,target) if target is not None else 0.)
        goals=[p]
        if target is not None:
            dx,dy=target[0]-p[0],target[1]-p[1]
            norm2=dx*dx+dy*dy
            if norm2>1e-8:
                alpha=max(0.,min(1.,((old[0]-p[0])*dx+(old[1]-p[1])*dy)/norm2))
                projection=(p[0]+alpha*dx,p[1]+alpha*dy)
                if math.dist(p,projection)>1e-5:
                    goals.append(projection)
        best=original;radius=base_radius;vertices=base_vertices;selected='unchanged'
        for goal_index,goal in enumerate(goals):
            lo,hi=0.,1.;proposal_best=original;proposal_radius=base_radius;proposal_vertices=base_vertices
            for _ in range(10):
                t=(lo+hi)/2.
                point=(goal[0]+t*(old[0]-goal[0]),goal[1]+t*(old[1]-goal[1]))
                proposal=original[:];proposal[index]=point
                self.counters['a1_cover_checks']+=1
                accepted,new_radius,new_vertices=a1_cover_certificate(proposal)
                if accepted:
                    hi=t;proposal_best=proposal;proposal_radius=new_radius;proposal_vertices=new_vertices
                else:
                    lo=t
            if goal_index==0:
                take=distance-math.dist(p,proposal_best[index])>=2.
            else:
                take=route_cost(proposal_best[index])<route_cost(best[index])-1e-6
            if take:
                best=proposal_best;radius=proposal_radius;vertices=proposal_vertices
                selected='incoming' if goal_index==0 else 'next-waypoint-projection'
        self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
        if best[index]==old:
            return task
        self.points=best
        gain=route_cost(old)-route_cost(best[index])
        assert gain>=-1e-6
        self.counters['a1_lookahead_station_moves']=self.counters.get('a1_lookahead_station_moves',0)+1
        self.counters['a1_station_two_leg_proxy_saved_m']=self.counters.get('a1_station_two_leg_proxy_saved_m',0.)+gain
        self.a1_cover_events.append(dict(index=index,old=old,new=best[index],points=best,
            station_shift=selected,route_successor=target,two_leg_proxy_saved_m=gain,
            covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
            unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
        return task

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1LookaheadStationSpatial(env,mode=mode,**merged)
        return _A1_LOOKAHEAD_STATION_PARENT(env,mode=mode,**merged)
