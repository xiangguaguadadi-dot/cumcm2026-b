import hashlib,json,pathlib,datetime
here=pathlib.Path(__file__).resolve().parent
baseline=(here.parent/'baseline.py').read_bytes()
expected='0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea'
assert hashlib.sha256(baseline).hexdigest()==expected
patch=(here/'patch_A1.py').read_bytes()
candidate=baseline+b'\n\n'+patch
(here/'candidate_A1.py').write_bytes(candidate)
record={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate':'candidate_A1.py','sha256':hashlib.sha256(candidate).hexdigest(),'parent_sha256':expected,'patch_sha256':hashlib.sha256(patch).hexdigest(),'mechanism':'same parent baseline length; polygon-dependent Q2 analytic and midpoint directions; actual current incoming travel cap; all-bearing sampled minimax MEC; radius/route-time gate; Q4 visibility prior gate, unchanged no-signal rescue','candidate_points_max':5,'second_observation_grid_intervals':80,'data_role':'already exposed local regression; no new blind or official testing','protected':'parent posterior update, optical certificates, finite optical coverage, channel/station discovery and fallback unchanged','decision_scope':'second_point only; one previous bearing; radius>100; 60<=baseline<=1000'}
(here/'registration_A1.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
