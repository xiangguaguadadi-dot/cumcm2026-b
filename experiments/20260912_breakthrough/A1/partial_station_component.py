"""D3: shorten a selected station's incoming leg under the same certificate."""
_A1_PARTIAL_STATION_PARENT=Solver
_A1_PARTIAL_SPATIAL_PARENT=A1RotatedMinimaxSpatial

class A1PartialStationSpatial(_A1_PARTIAL_SPATIAL_PARENT):
    def spatial_next_task(self,todo):
        task=super().spatial_next_task(todo)
        if not task or task[0]!='station' or task[1]==0 or self.virtual_time>=180000.:
            return task
        index=task[1]
        p=self.position
        old=self.points[index]
        distance=math.dist(p,old)
        if distance<2.:
            return task
        # The chosen index is still unvisited; all previously scanned sites
        # retain their real coordinates. This cannot invent negative evidence.
        assert index in todo
        assert all(index not in self.scanned[ch] for ch in range(1,21)
                   if not self.observations[ch] and ch not in self.cleared)
        start=time.perf_counter()
        lo,hi=0.,1.
        best=self.points[:]
        safe,radius,vertices=a1_cover_certificate(best)
        self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
        if not safe:
            self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
            return task
        for _ in range(10):
            t=(lo+hi)/2.
            point=(p[0]+t*(old[0]-p[0]),p[1]+t*(old[1]-p[1]))
            proposal=self.points[:]
            proposal[index]=point
            self.counters['a1_cover_checks']+=1
            accepted,new_radius,new_vertices=a1_cover_certificate(proposal)
            if accepted:
                hi=t;best=proposal;radius=new_radius;vertices=new_vertices
            else:
                lo=t
        self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
        saved=distance-math.dist(p,best[index])
        if saved<2.:
            return task
        self.points=best
        self.counters['a1_partial_station_moves']=self.counters.get('a1_partial_station_moves',0)+1
        self.counters['a1_partial_incoming_saved_m']=self.counters.get('a1_partial_incoming_saved_m',0.)+saved
        self.a1_cover_events.append(dict(index=index,old=old,new=best[index],points=best,
            partial_incoming_leg=True,incoming_distance_saved_m=saved,
            covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
            unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
        # Keep the same selected station and downstream service successor.
        # For a fixed subsequent waypoint, shortening this incoming segment
        # cannot increase the two-edge Euclidean path (triangle inequality).
        # Unknown observations may change later tasks; this is not a whole-run
        # nonregression guarantee and actual candidate evaluation is required.
        return task

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1PartialStationSpatial(env,mode=mode,**merged)
        return _A1_PARTIAL_STATION_PARENT(env,mode=mode,**merged)
