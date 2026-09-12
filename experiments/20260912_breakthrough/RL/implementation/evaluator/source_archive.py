"""Archive exact source bytes; verify every member against the recorded freeze."""
import hashlib
import json
from pathlib import Path
import zipfile
from ..deploy.vendor import REPO


def archive_sources(freeze,path,*,overrides=None,provenance='archived_before_environment_execution'):
    path=Path(path)
    if path.exists():raise FileExistsError('Immutable source archive already exists')
    overrides=overrides or {};members={}
    for name,expected in freeze['files'].items():
        data=overrides[name] if name in overrides else (REPO/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:
            raise RuntimeError('Cannot archive changed source bytes: '+name)
        members[name]=data
    manifest=dict(schema='bc-rpi-exact-source-archive-v1',provenance=provenance,
                  files=freeze['files'],reconstructed_members=sorted(overrides))
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(members.items()):z.writestr(name,data)
        z.writestr('_SOURCE_ARCHIVE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise RuntimeError('Source zip CRC validation failed')
        for name,expected in freeze['files'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:
                raise RuntimeError('Archived source member differs')
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                members=len(members),provenance=provenance,reconstructed_members=sorted(overrides))
