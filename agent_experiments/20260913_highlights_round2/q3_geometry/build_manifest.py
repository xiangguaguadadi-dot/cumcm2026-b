#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
exclude = {"artifact_manifest.json"}
rows = {}
for p in sorted(HERE.iterdir()):
    if p.is_file() and p.name not in exclude:
        rows[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
(HERE / "artifact_manifest.json").write_text(json.dumps({
    "scope": "q3_geometry isolated round2 artifacts",
    "self_excluded": "artifact_manifest.json",
    "files": rows,
}, ensure_ascii=False, indent=2) + "\n")
print(len(rows), "files")
