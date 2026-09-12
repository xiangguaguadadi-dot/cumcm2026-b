#!/usr/bin/env python3
"""Independently check stage zip members, embedded hashes and exact live bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from audit_rl_execution import read_json,require,sha256


def audit(repo,preflight):
    repo,preflight=Path(repo).resolve(),Path(preflight).resolve();checks=[];sources={}
    for role,archive_name in [('source','sources'),('input','inputs')]:
        freeze_path=preflight/(role+'_freeze.json');record_path=preflight/(role+'_archive.json')
        archive_path=preflight/(archive_name+'.zip')
        freeze=read_json(freeze_path);record=read_json(record_path)
        require(sha256(archive_path)==record['sha256'] and record['members']==len(freeze['files']), 'Archive digest/count mismatch')
        with zipfile.ZipFile(archive_path) as z:
            names=z.namelist();require(z.testzip() is None,'Zip CRC failure')
            require(len(names)==len(set(names)) and set(names)==set(freeze['files'])|{'_SOURCE_ARCHIVE_MANIFEST.json'},'Archive member set differs')
            embedded=json.loads(z.read('_SOURCE_ARCHIVE_MANIFEST.json'))
            require(embedded['files']==freeze['files'] and embedded['provenance']==record['provenance']
                    and embedded['reconstructed_members']==record['reconstructed_members'],'Embedded archive manifest differs')
            for name, expected in freeze['files'].items():
                path=(repo/name).resolve();require(path.is_relative_to(repo),'Archived path outside repo')
                require(sha256(path)==hashlib.sha256(z.read(name)).hexdigest()==expected,'Archived/live content mismatch: '+name)
                sources[str(path)]=expected
        for path in (freeze_path,record_path,archive_path):sources[str(path)]=sha256(path)
        checks.append(dict(role=role,members=len(freeze['files']),archive_sha256=record['sha256']))
    require(all(sha256(p)==s for p,s in sources.items()),'Stage source/input changed during audit')
    return dict(status='source_and_input_archives_exactly_verified',checks=checks,source_sha256=sources,
                actual_environment_calls=0,actual_optimizer_updates=0,auditor_sha256=sha256(__file__))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','preflight','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Preserve previous audit')
    result=audit(a.repo,a.preflight);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','checks')},indent=2))
