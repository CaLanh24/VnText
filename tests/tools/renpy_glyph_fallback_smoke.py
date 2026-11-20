"""Engine proof for the symbol glyph fallback: the generated FontGroup style loads in real Ren'Py, splits "Mở ♫" between the preferred font and the bundled
fallback, and both font files load as real FreeType fonts.  Headless (dummy video/audio), bounded, writes only under its own work directory.

    python tests/tools/renpy_glyph_fallback_smoke.py --sdk .dev-env/tools/renpy-8.5.3 --work TEST_RUN/glyph-fallback-smoke
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PROBE = '''
init python:
    import json
    def _probe():
        import renpy.text.font as F
        out = {"language": renpy.game.preferences.language}
        font = style.default.font
        out["is_group"] = isinstance(font, F.FontGroup)
        with open(renpy.config.basedir + "/symbol.txt", "rb") as handle:
            symbol = handle.read().decode("utf-8")
        segments = list(font.segment(u"M\\u1edf " + symbol)) if out["is_group"] else []
        out["segments"] = [[name, text] for name, text in segments]
        loaded = {}
        for name in sorted({name for name, _ in segments}):
            try:
                fo = F.get_font(name, 24, False, False, 0, True, False, True, 1.0, "freetype", None, None, None)
                loaded[name] = type(fo).__name__
            except Exception as exc:
                loaded[name] = "ERR " + repr(exc)[:80]
        out["loaded"] = loaded
        with open(renpy.config.basedir + "/probe.json", "w") as handle:
            json.dump(out, handle)
label start:
    $ _probe()
    $ renpy.quit()
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    sdk = Path(args.sdk).resolve()
    work = Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    from tests.unit import test_renpy_patch
    from tests.unit.test_renpy_font_lacking_vietnamese import LATIN, VIETNAMESE, sfnt
    from vntext.patch_renpy import apply_renpy_translation_package

    with tempfile.TemporaryDirectory(dir=work) as temp:
        base = Path(temp)
        game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
        # a preferred font the engine can really load (Inter has Vietnamese); pick a symbol it lacks but the bundled fallback has, by the product's cmap gate
        from vntext.font_coverage import cmap_glyphs
        preferred = ROOT / "wpf_app/VNText.Studio.App/Assets/Fonts/Inter-Regular.ttf"
        fallback_bytes = (ROOT / "vntext/fonts/DejaVuSans.ttf").read_bytes()
        candidates = [0x266B, 0x266A, 0x2603, 0x260E, 0x2694, 0x265E, 0x2698, 0x2622, 0x2620, 0x262F]
        lacking = cmap_glyphs(preferred.read_bytes(), candidates)["missing"]
        symbols = [cp for cp in candidates if f"U+{cp:04X}" in " ".join(lacking) and not cmap_glyphs(fallback_bytes, [cp])["missing"]]
        if not symbols:
            print(json.dumps({"pass": False, "stage": "setup", "error": "no symbol that the preferred font lacks and the fallback has", "lacking": lacking}))
            return 1
        symbol = chr(symbols[0])
        csv.write_bytes(csv.read_bytes().replace("Mở".encode(), ("Mở " + symbol).encode()))
        out = base / "out"
        try:
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out), replacement_font=str(preferred))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"pass": False, "stage": "generate", "error": str(exc)}))
            return 1
        evidence = json.loads((out / "font_preflight.json").read_text(encoding="utf-8"))
        if "glyph_fallback" not in evidence:
            print(json.dumps({"pass": True, "note": "preferred font already covers every symbol; nothing to prove", "glyph_status": evidence["glyph_status"]}))
            return 0
        project = work / "project"
        shutil.copytree(out / "COPY_TO_GAME_ROOT", project)
        (project / "game").mkdir(exist_ok=True)
        (project / "symbol.txt").write_bytes(symbol.encode("utf-8"))
        (project / "game/probe.rpy").write_text("default name = 'X'\n" + PROBE, encoding="utf-8")
        (project / "game/options.rpy").write_text("define config.save_directory = None\ndefine config.developer = True\n", encoding="utf-8")
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", RENPY_RENDERER="sw")
        try:
            process = subprocess.run([str(sdk / "lib/py3-windows-x86_64/python.exe"), "-B", str(sdk / "renpy.py"), str(project)], cwd=str(sdk), env=env,
                                     capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            errors = project / "errors.txt"
            print(json.dumps({"pass": False, "stage": "engine", "error": "timeout", "errors_txt": errors.read_text(encoding="utf-8-sig")[:800] if errors.is_file() else ""}))
            return 1
        probe_path = project / "probe.json"
        if not probe_path.is_file():
            print(json.dumps({"pass": False, "stage": "engine", "returncode": process.returncode, "stderr": process.stderr[-600:]}))
            return 1
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
        names = [name for name, _ in probe["segments"]]
        primary = evidence["payload_font"].split("/", 1)[1]
        fallback = evidence["glyph_fallback"]["payload_font"].split("/", 1)[1]
        ok = (probe["language"] == "vietnamese" and probe["is_group"]
              and probe["segments"][0][1].startswith("M") and probe["segments"][-1][1] == symbol
              and names[0] == primary and names[-1] == fallback
              and all(value == "FTFont" for value in probe["loaded"].values()) and len(probe["loaded"]) == 2)
        print(json.dumps({"pass": ok, "probe": probe, "primary_missing": evidence["primary_missing"], "glyph_status": evidence["glyph_status"]}, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
