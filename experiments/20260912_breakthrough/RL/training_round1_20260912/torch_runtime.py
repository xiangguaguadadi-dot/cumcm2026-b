"""Use the already-installed dedicated runtime without running site/.pth hooks."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys

SITE=Path('/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/lib/python3.12/site-packages')

def configure():
    if not sys.flags.no_site:raise RuntimeError('Neural workers require explicit Python -S -B')
    if not (SITE/'torch/__init__.py').is_file():raise RuntimeError('Approved dedicated Torch runtime missing')
    if str(SITE) not in sys.path:sys.path.append(str(SITE))
    import torch,numpy
    if str(torch.__version__)!='2.8.0' or numpy.__version__!='2.2.6':
        raise RuntimeError('Approved Torch/Numpy versions changed')
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    return torch

def identity():
    torch=configure();import numpy
    paths=[Path(torch.__file__),Path(torch._C.__file__),Path(numpy.__file__)]
    paths+=sorted((SITE/'torch/lib').glob('*.dylib'))
    paths+=sorted((SITE/'torch/lib').glob('*.so'))
    return dict(python_executable=sys.executable,python_version=sys.version,no_site=sys.flags.no_site,
        site_hooks_executed=False,torch=str(torch.__version__),numpy=numpy.__version__,
        threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),device='cpu',
        runtime_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
