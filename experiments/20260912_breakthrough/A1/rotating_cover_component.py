"""D3 R7: jointly rotate only future sites to fit a certified paid stop."""
_A1_ROTATING_COVER_PARENT=Solver
class A1RotatingCoverSpatial(A1CoverSpatial):
    def spatial_next_task(self,todo):
        p=self.position
        eligible=(todo and 0 not in todo and self.virtual_time<180000. and
                  self._a1_last_cover_stop!=p and
                  not any(math.dist(p,self.points[i])<1e-5 for i in range(len(self.points)) if i not in todo))
        if eligible:
            self._a1_last_cover_stop=p
            for index in sorted(todo,key=lambda i:(math.dist(p,self.points[i]),i)):
                if math.dist(p,self.points[index])>1000.:continue
                old=self.points[index]
                delta=math.atan2(p[1],p[0])-math.atan2(old[1],old[0])
                delta=(delta+math.pi)%(2*math.pi)-math.pi
                if abs(delta)>math.pi/6:continue
                for angle in (0.,delta):
                    proposal=self.points[:]
                    cc,ss=math.cos(angle),math.sin(angle)
                    for j in todo:
                        q=self.points[j]
                        proposal[j]=(cc*q[0]-ss*q[1],ss*q[0]+cc*q[1])
                    proposal[index]=p
                    self.counters['a1_cover_checks']=self.counters.get('a1_cover_checks',0)+1
                    start=time.perf_counter()
                    safe,radius,vertices=a1_cover_certificate(proposal)
                    self.counters['a1_cover_cpu_s']=self.counters.get('a1_cover_cpu_s',0.)+time.perf_counter()-start
                    if not safe:continue
                    assert all(j not in self.scanned[ch] for j in todo for ch in range(1,21)
                               if not self.observations[ch] and ch not in self.cleared)
                    self.points=proposal
                    self.counters['a1_cover_replacements']=self.counters.get('a1_cover_replacements',0)+1
                    self.counters['a1_cover_rotations']=self.counters.get('a1_cover_rotations',0)+int(abs(angle)>1e-10)
                    self.a1_cover_events.append(dict(index=index,old=old,new=p,points=proposal,rotation=angle,
                        covering_radius_upper=radius,vertices=vertices,virtual_time_s=self.virtual_time,
                        unknown=[ch for ch in range(1,21) if not self.observations[ch] and ch not in self.cleared]))
                    self.route_successor=None
                    return 'station',index
        return A1ServiceSpatial.spatial_next_task(self,todo)

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return A1RotatingCoverSpatial(env,mode=mode,**merged)
        return _A1_ROTATING_COVER_PARENT(env,mode=mode,**merged)
