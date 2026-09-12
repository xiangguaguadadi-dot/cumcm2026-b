"""R6: whole-task learned advantage gates one complete source-service macro.

Requires the frozen R3 observation-residual class and its tail config to be
bound first. No environment cloning, evaluation data or source truths here.
"""
class WholeTaskResidualDirectional(ObservationResidualDirectional):
    def localize(self,ch):
        saved_style=self.config.get('a3_style','learned')
        if len(self.observations[ch])>=2 and self._e2_progress.get(ch,0)<9:
            center,radius=_C7._Q4._di_enclosing_circle(self.polygons[ch])
            if 20.<radius<=100.:
                q=_a3_estimate(self.observations[ch],center,self.polygons[ch])
                f=_a3_features(self,ch,center,radius,q)
                heads=self.config['r6_heads']
                scores={style:sum(a*b for a,b in zip(weights,f)) for style,weights in heads.items()}
                choice=max(scores,key=scores.get)
                if scores[choice]>self.config['r6_threshold']:
                    self.config['a3_style']=choice
                    self.counters['r6_service_interventions']=self.counters.get('r6_service_interventions',0)+1
        try:return super().localize(ch)
        finally:self.config['a3_style']=saved_style

class Solver:
    def __new__(cls,env,mode=3,**config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        return _A3_Q3.Solver(env,mode=3,**merged) if mode==3 else WholeTaskResidualDirectional(env,mode=4,**merged)
