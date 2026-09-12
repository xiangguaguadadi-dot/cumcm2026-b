"""Read-only, SHA-pinned reuse of approved controller/guard primitives.

No original source is changed. The private package name avoids old `core`
module collisions. Imported files use only public controller/interface data.
"""
from __future__ import annotations
import hashlib
import importlib.util
import importlib
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[5]
OLD = REPO / 'experiments/20260911_rl_execution/core'
PINS = {
    '__init__.py': '9945e9aed1ffb85144b35a1afbdc2fb6ff86d66929f2cd96977492b9b3771bc1',
    'schema.py': '2ef71e8a18dc068847e070e13ff469916abeaf46588036cb4d1d602f4f9c2f68',
    'engine.py': 'dd143ba911a7e6bd46a79fe7ae5d98bd98681e7d20764b57436c321e1af0894c',
    'interface.py': 'ed5d3e98ab846dc546f9e5d5adcbc8e8c63e936e99e1f5f2cdf1096dd77042f3',
    'fallback.py': 'fcc07db4e62341cbdc8d20335096d3541bacfbbdbd1614bf3c1a5936525f00c3',
    'geometry.py': 'a7a5a98efe5be405e45f796421b35eb1ecdad07bcb3977774d45a3bcedd764a3',
}
for name, digest in PINS.items():
    if hashlib.sha256((OLD / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Frozen dependency changed: ' + name)
PACKAGE = '_bc_rpi_frozen_core'
if PACKAGE not in sys.modules:
    spec = importlib.util.spec_from_file_location(PACKAGE, OLD / '__init__.py', submodule_search_locations=[str(OLD)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    spec.loader.exec_module(package)
engine = importlib.import_module(PACKAGE + '.engine')
interface = importlib.import_module(PACKAGE + '.interface')
geometry = importlib.import_module(PACKAGE + '.geometry')
fallback = importlib.import_module(PACKAGE + '.fallback')
GuardConfig = interface.GuardConfig
FallbackRequired = interface.FallbackRequired
InterfaceFailure = interface.InterfaceFailure
C7_SHA256 = engine.C7_SHA256

_CLASSES = {}


def implementation_hash():
    """Bind all deploy helpers and all actually imported frozen core files."""
    files = sorted(Path(__file__).parent.glob('*.py'))
    entries = [(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    entries += [('frozen/' + k, v) for k, v in sorted(PINS.items())]
    return hashlib.sha256(repr(entries).encode()).hexdigest()


def load_c7():
    module = engine.load_c7()
    if (Path(module.__file__).parent / 'coverage_points.json').exists():
        raise RuntimeError('Unexpected C7 coverage sidecar invalidates frozen deployment')
    return module


def _clock_guard(self):
    # Literal original condition/message; only clock source is injectable.
    if self.deadline and self.env.clock() > self.deadline:
        raise TimeoutError('Remaining real-time budget nearly exhausted; completeness not certified')


def make_controller(api, mode):
    s = load_c7().Solver(api, mode=mode)
    original_type = type(s)
    if original_type not in _CLASSES:
        _CLASSES[original_type] = type('ClockBound_' + original_type.__name__, (original_type,), {'_time_guard': _clock_guard})
    s.__class__ = _CLASSES[original_type]
    return s


class NoCalls:
    """Detached candidate generation has no live API or evaluator handle."""
    def _forbidden(self, *args, **kwargs):
        raise RuntimeError('Detached preparation attempted an interface call')
    enter = measure = clear = exit = clock = _forbidden
