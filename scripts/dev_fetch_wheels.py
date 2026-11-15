"""Dev-only helper: install pure-Python wheels without pip's unpack step.

Some restricted Windows sandboxes deny pip's temporary unpack directory even
though the workspace itself is writable. This script resolves a small, explicit
dependency set from the PyPI JSON API, downloads the best-matching wheel, and
extracts it straight into a target directory.

The delivered application does NOT need this file: a normal `pip install -r
requirements.txt` works on a standard Python installation. It exists so the
project can also be built in locked-down environments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import zipfile

# name -> extras resolved by hand (fastapi/uvicorn core only, no C accelerators)
PACKAGES = [
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_extensions",
    "typing_inspection",
    "anyio",
    "idna",
    "sniffio",
    "uvicorn",
    "click",
    "h11",
    "colorama",
]


def wheel_rank(filename: str) -> int:
    """Prefer native cp wheels, then abi3, then pure-python."""
    tags = (
        "cp312-cp312-win_amd64",
        "cp311-cp311-win_amd64",
        "abi3-win_amd64",
        "py3-none-any",
    )
    for i, tag in enumerate(tags):
        if tag in filename:
            return i
    return 99


def fetch(spec: str, target: str) -> str:
    name, _, pinned = spec.partition("==")
    url = f"https://pypi.org/pypi/{name}/json"
    with urllib.request.urlopen(url, timeout=60) as r:
        meta = json.load(r)
    version = pinned or meta["info"]["version"]
    files = [f for f in meta["releases"].get(version, []) if f["filename"].endswith(".whl")]
    if not files:
        raise SystemExit(f"no wheel for {name} {version}")
    files.sort(key=lambda f: wheel_rank(f["filename"]))
    best = files[0]
    if wheel_rank(best["filename"]) > 10:
        raise SystemExit(f"no compatible wheel for {name}: {[f['filename'] for f in files][:5]}")
    dest = os.path.join(target, "_wheels", best["filename"])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        with urllib.request.urlopen(best["url"], timeout=180) as r, open(dest, "wb") as fh:
            fh.write(r.read())
    with zipfile.ZipFile(dest) as zf:
        zf.extractall(target)
    return f"{name}=={version} ({best['filename']})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=".pydeps")
    ap.add_argument("--packages", nargs="*", default=PACKAGES)
    args = ap.parse_args()
    os.makedirs(args.target, exist_ok=True)
    for pkg in args.packages:
        try:
            print("  ", fetch(pkg, args.target))
        except SystemExit as exc:
            print("  !!", exc)
            return 1
    print("done ->", os.path.abspath(args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
