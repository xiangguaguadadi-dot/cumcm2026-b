"""Read-only public-source acquisition; never imports solver or training packages.

Run with python3.12 -S -B. Downloads stay below RL/sources. No site packages or
pth files are evaluated. The wheel is a pinned, isolated PDF text reader only.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "sources"
OUT.mkdir(exist_ok=True)
PYPDF = "https://files.pythonhosted.org/packages/58/13/645df3995075112cb3cce15e8797c205f0f88fb50acc11012b84b071bc22/pypdf-6.18.1-py3-none-any.whl"
SOURCES = [
    ("S01_dagger", "https://proceedings.mlr.press/v15/ross11a.html", "https://proceedings.mlr.press/v15/ross11a/ross11a.pdf"),
    ("S02_lols", "https://proceedings.mlr.press/v37/changb15.html", "https://proceedings.mlr.press/v37/changb15.pdf"),
    ("S03_aggrevated", "https://proceedings.mlr.press/v70/sun17d.html", "https://proceedings.mlr.press/v70/sun17d/sun17d.pdf"),
    ("S04_spibb", "https://proceedings.mlr.press/v97/laroche19a.html", "https://proceedings.mlr.press/v97/laroche19a/laroche19a.pdf"),
    ("S05_residual", "https://arxiv.org/abs/1812.03201v2", "https://arxiv.org/pdf/1812.03201v2"),
    ("S06_aggrevate", "https://arxiv.org/abs/1406.5979", "https://arxiv.org/pdf/1406.5979"),
    ("S07_catnipp", "https://proceedings.mlr.press/v205/cao23b.html", "https://proceedings.mlr.press/v205/cao23b/cao23b.pdf"),
    ("S08_offripp", "https://arxiv.org/abs/2409.16830", "https://arxiv.org/pdf/2409.16830"),
    ("S09_rf", "https://arxiv.org/abs/2605.12569v1", "https://arxiv.org/html/2605.12569v1"),
    ("S10_multistep", "https://arxiv.org/abs/2609.03842", "https://arxiv.org/html/2609.03842v1"),
    ("S11_shield", "https://arxiv.org/abs/1708.08611", "https://arxiv.org/pdf/1708.08611"),
    ("S12_robust_ipp", "https://arxiv.org/abs/2410.17186", "https://arxiv.org/html/2410.17186v2"),
    ("S13_recurrent", "https://arxiv.org/abs/2405.15384", "https://arxiv.org/html/2405.15384v3"),
    ("S14_tdmpc2", "https://arxiv.org/abs/2310.16828", None),
    ("S15_fql", "https://arxiv.org/abs/2502.02538", None),
    ("S16_cids", "https://arxiv.org/abs/2602.03939", None),
]

def acquire(url: str, path: Path):
    proc = subprocess.run(["curl", "--noproxy", "*", "-fLsS", "--max-time", "45", url], capture_output=True)
    row = {"url": url, "accessed_utc": datetime.now(timezone.utc).isoformat(), "returncode": proc.returncode}
    if proc.returncode == 0:
        path.write_bytes(proc.stdout)
        row.update(path=str(path.relative_to(ROOT)), bytes=len(proc.stdout), sha256=hashlib.sha256(proc.stdout).hexdigest())
    else:
        row["error"] = proc.stderr.decode(errors="replace")[:2000]
    return row

def html_text(data: str):
    data = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", data, flags=re.S|re.I)
    data = re.sub(r"</(?:p|div|section|h[1-6]|li|tr)>", "\n", data)
    return html.unescape(re.sub(r"<[^>]+>", " ", data))

def main():
    parser_path = OUT / "pypdf-6.18.1-py3-none-any.whl"
    parser_log = acquire(PYPDF, parser_path)
    if parser_log["returncode"]: raise RuntimeError(parser_log)
    sys.path.insert(0, str(parser_path))
    from pypdf import PdfReader
    def one(source):
        sid, page_url, body_url = source
        page = OUT / f"{sid}.html"
        logs = [acquire(page_url, page)]
        meta = {}
        if page.exists():
            raw = page.read_text(errors="replace")
            for key, value in re.findall(r'<meta\s+name="(citation_[^"]+)"\s+content="([^"]*)"', raw):
                meta.setdefault(key, []).append(html.unescape(value))
            (OUT / f"{sid}.metadata.txt").write_text(html_text(raw))
        if body_url:
            is_html = "/html/" in body_url
            body = OUT / (f"{sid}.body.html" if is_html else f"{sid}.pdf")
            logs.append(acquire(body_url, body))
            if body.exists():
                if is_html:
                    (OUT / f"{sid}.txt").write_text(html_text(body.read_text(errors="replace")))
                else:
                    reader = PdfReader(body)
                    text = "\n\n".join(f"=== PDF PAGE {i+1} ===\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))
                    (OUT / f"{sid}.txt").write_text(text)
        return {"id": sid, "metadata": meta, "acquisitions": logs}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, SOURCES))
    (OUT / "acquisition.json").write_text(json.dumps({"parser": parser_log, "sources": records}, ensure_ascii=False, indent=2))
    for r in records:
        print(r["id"], r["metadata"].get("citation_title"), [l["returncode"] for l in r["acquisitions"]])

if __name__ == "__main__": main()
