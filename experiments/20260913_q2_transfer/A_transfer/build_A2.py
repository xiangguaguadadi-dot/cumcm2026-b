"""Pre-register one mechanism ablation: remove the downstream radius-time gate."""
import hashlib,json,pathlib,datetime
here=pathlib.Path(__file__).resolve().parent
baseline=(here.parent/'baseline.py').read_bytes()
assert hashlib.sha256(baseline).hexdigest()=='0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea'
patch=(here/'patch_A1.py').read_text()
patch=patch.replace('Q2 transfer A1: same-baseline angular designs, robust accuracy and cost gate.', 'Q2 transfer A2: same-baseline minimax accuracy without downstream cost gate.')
patch=patch.replace('best=old;best_gain=1.','best=old;best_r=old_r')
old='''            # All terms are seconds: approach/exit movement, unresolved
            # optical search radius, and inherited visibility failure penalty.
            benefit=(max(0.,old_r-20.)-max(0.,r-20.))/5.
            cost=(route-old_route)/5.+120.*max(0.,old_visibility-visibility)
            gain=benefit-cost
            if gain>best_gain:
                best,best_gain=q,gain'''
new='''            # Mechanism ablation: after the unchanged movement and Q4
            # visibility gates, choose only by bounded-error localization.
            # This deliberately tests whether better precision itself helps
            # the existing full task; no downstream time benefit is asserted.
            if r<best_r-1e-8:
                best,best_r=q,r'''
assert old in patch;patch=patch.replace(old,new)
patch=patch.replace("self.counters['q2a_proxy_gain_s']=self.counters.get('q2a_proxy_gain_s',0.)+best_gain", "self.counters['q2a_radius_reduction_m']=self.counters.get('q2a_radius_reduction_m',0.)+old_r-best_r")
(here/'patch_A2.py').write_text(patch)
candidate=baseline+b'\n\n'+patch.encode();(here/'candidate_A2.py').write_bytes(candidate)
record={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate':'candidate_A2.py','sha256':hashlib.sha256(candidate).hexdigest(),'parent_sha256':hashlib.sha256(baseline).hexdigest(),'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'mechanism':'A1 mechanism ablation: same candidate directions, same first-baseline length and actual incoming travel cap, same Q4 visibility gate; choose lowest worst MEC directly, removing radius-to-downstream-time gate','reason':'A1 quick changed only one Q3 case and no Q4 outcomes; directly test whether minimizing uncertainty can reduce full task cost','data_role':'existing exposed regression; not blind or official','max_versions_this_route':3}
(here/'registration_A2.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
