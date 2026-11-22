"""Engine proof for the font size option: the generated scale block runs in real Ren'Py (language-scoped), config.ftfont_scale carries the value for the
generated Vietnamese font only, and the loaded font really measures that much smaller.  Headless (dummy video/audio), bounded, writes only under its work dir.

    python tests/tools/renpy_font_scale_smoke.py --sdk .dev-env/tools/renpy-8.5.3 --work TEST_RUN/font-scale-smoke [--scale 0.8]
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
        out = {"language": renpy.game.preferences.language, "scale_map": dict(renpy.config.ftfont_scale)}
        with open(renpy.config.basedir + "/fontname.txt") as handle:
            name = handle.read().strip()
        def width():
            F.font_cache.clear()
            try:
                renpy.text.text.layout_cache_clear()
            except Exception:
                pass
            label = renpy.text.text.Text(u"Xin ch\\u00e0o c\\u00e1c b\\u1ea1n, h\\u1eb9n g\\u1eb7p l\\u1ea1i", font=name, size=40, style="default")
            return renpy.render(label, 4000, 400, 0, 0).get_size()[0]
        out["scaled_width"] = width()
        saved = renpy.config.ftfont_scale.pop(name, None)
        out["plain_width"] = width()
        if saved is not None:
            renpy.config.ftfont_scale[name] = saved
        with open(renpy.config.basedir + "/probe.json", "w") as handle:
            json.dump(out, handle)
label start:
    python:
        try:
            _probe()
        except Exception as _exc:
            with open(renpy.config.basedir + "/probe.json", "w") as _handle:
                json.dump({"error": repr(_exc)}, _handle)
    $ renpy.quit()
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--scale", type=float, default=0.8)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    sdk = Path(args.sdk).resolve()
    work = Path(args.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    from tests.unit import test_renpy_patch
    from vntext.patch_renpy import apply_renpy_translation_package

    with tempfile.TemporaryDirectory(dir=work) as temp:
        base = Path(temp)
        game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
        preferred = ROOT / "wpf_app/VNText.Studio.App/Assets/Fonts/Inter-Regular.ttf"
        out = base / "out"
        try:
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out), replacement_font=str(preferred), font_scale=args.scale)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"pass": False, "stage": "generate", "error": str(exc)}))
            return 1
        evidence = json.loads((out / "font_preflight.json").read_text(encoding="utf-8"))
        project = work / "project"
        shutil.copytree(out / "COPY_TO_GAME_ROOT", project)
        font_name = evidence["payload_font"].split("/", 1)[1]
        (project / "fontname.txt").write_text(font_name, encoding="utf-8")
        (project / "game").mkdir(exist_ok=True)
        (project / "game/probe.rpy").write_text("default name = 'X'\n" + PROBE, encoding="utf-8")
        (project / "game/options.rpy").write_text("define config.save_directory = None\ndefine config.developer = True\n", encoding="utf-8")
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", RENPY_RENDERER="sw")
        try:
            process = subprocess.run([str(sdk / "lib/py3-windows-x86_64/python.exe"), "-B", str(sdk / "renpy.py"), str(project)], cwd=str(sdk), env=env,
                                     capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(json.dumps({"pass": False, "stage": "engine", "error": "timeout"}))
            return 1
        probe_path = project / "probe.json"
        if not probe_path.is_file():
            print(json.dumps({"pass": False, "stage": "engine", "returncode": process.returncode, "stderr": process.stderr[-600:]}))
            return 1
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
        ratio = probe["scaled_width"] / probe["plain_width"] if probe["plain_width"] else 0
        only_ours = set(probe["scale_map"]) - {"_OpenDyslexic3-Regular.ttf"} == {font_name}   # the engine's own accessibility entry is not ours; nothing else may appear
        ok = (probe["language"] == "vietnamese" and probe["scale_map"].get(font_name) == round(args.scale, 2) and only_ours
              and abs(ratio - args.scale) <= 0.08)
        print(json.dumps({"pass": ok, "scale": args.scale, "measured_ratio": round(ratio, 3), "probe": probe}, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
