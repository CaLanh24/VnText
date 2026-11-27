"""Rebuild an installed-layout baseline from a published Setup.exe (needed by the update tests).

  python release/extract_setup_payload.py VNTextStudio-0.1.NN-Setup.exe OUT_DIR

Compiles release/ResourceDump.cs with the .NET Framework csc (no SDK needed), dumps the embedded Payload.zip and extracts it into OUT_DIR.
The Setup must come from a public GitHub release whose sha256 was checked first; the helper exe and zip are removed afterwards.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 64
    setup, out = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    source = Path(__file__).with_name("ResourceDump.cs")
    with tempfile.TemporaryDirectory(prefix="vnt-rd-") as tmp:
        exe, payload = Path(tmp) / "ResourceDump.exe", Path(tmp) / "Payload.zip"
        subprocess.run([str(CSC), "/nologo", "/target:exe", f"/out:{exe}", str(source)], check=True)
        subprocess.run([str(exe), str(setup), str(payload)], check=True, timeout=600)
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(payload) as z:
            z.extractall(out)
    print((out / "app" / "VERSION.txt").read_text(encoding="utf-8").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
