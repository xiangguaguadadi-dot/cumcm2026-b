"""D1: task-value gating of existing paid-station Q3 retests only."""
_A1_PARENT = Solver

class A1StationSpatial(_Q3._LensSpatial):
    def scan_station(self,index,defer=False):
        if not defer or not self.config.get('a1_station_gate',True):
            return super().scan_station(index,defer=defer)
        p=self.points[index]
        unknown=[c for c in range(1,21) if c not in self.cleared and not self.observations[c]]
        if self.channel in unknown:
            unknown.remove(self.channel);unknown.insert(0,self.channel)
        self.counters['scan_stations']+=1
        for ch in unknown:
            self.measure(p,ch)
            self.scanned[ch].add(index)
        # Preserve C7's origin-silent adaptive certified ring verbatim.
        if (self.mode==3 and index==0 and not self.cleared and
                not any(self.observations.values()) and
                self.config.get('adaptive_ring',True) and
                not any(i!=0 for indices in self.scanned.values() for i in indices)):
            rr=1800*math.cos(math.pi/6)
            self.points=[(0.,0.)]+[(rr*math.cos(i*math.pi/3),rr*math.sin(i*math.pi/3)) for i in range(6)]
        for ch in range(1,21):
            if ch in self.cleared or not self.observations[ch]:continue
            if any(math.dist(p,old)<1e-5 for old,_ in self.observations[ch]):continue
            center,radius=_Q3._sp_enclosing_circle(self.polygons[ch])
            if math.dist(center,p)>1500.+radius:continue
            self.counters['a1_station_considered']=self.counters.get('a1_station_considered',0)+1
            if radius<=20.:
                take=False
            else:
                prediction=self._gate_prediction(ch,p)
                take=prediction is None or prediction[1]>0.
            if take:
                self.counters['a1_station_taken']=self.counters.get('a1_station_taken',0)+1
                self.measure(p,ch)
            else:
                self.counters['a1_station_skipped']=self.counters.get('a1_station_skipped',0)+1

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1StationSpatial(env,mode=mode,**merged)
        return _A1_PARENT(env,mode=mode,**merged)
