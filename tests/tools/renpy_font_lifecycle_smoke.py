"""Headless Ren'Py lifecycle smoke: the generated font replacement survives a game that assigns its own config.font_replacement_map.

usage: renpy_font_lifecycle_smoke.py <new_work_dir> <sdk_dir> <evidence_json>
Probes the map through title-less start, a game-side `config.font_replacement_map = {...}` assignment and the following interactions (real Ren'Py, dummy SDL,
software renderer).  Without the guard (0.1.25 generator) the replacement stays lost after the assignment; with it the wrapper is back at the next interaction.
"""
import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vntext.patch_renpy import _render_activation  # noqa: E402
from vntext.renpy_font_support import prepare_font_support  # noqa: E402

LATIN = [ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"]
SCRIPT = '''init python:
    _probes = []
    def _probe(tag):
        got = config.font_replacement_map.get(("Gothic.ttf", False, False), ("Gothic.ttf", False, False))
        _probes.append((tag, renpy.game.preferences.language, type(config.font_replacement_map).__name__, got[0][-12:]))
        import json
        with open(renpy.config.basedir + "/lifecycle-out.json", "w") as handle:
            json.dump(_probes, handle)

label start:
    $ _probe("start")
    $ config.font_replacement_map = {("Other.ttf", True, False): ("Other-Bold.ttf", False, False)}
    $ _probe("game assigned its own config.font_replacement_map")
    $ renpy.pause(0.01)
    $ _probe("after the next interaction")
    $ renpy.pause(0.01)
    $ _probe("second interaction")
    $ renpy.quit()
    return
'''


def sfnt(codepoints):
    groups = b"".join(struct.pack(">LLL", c, c, 3 + i) for i, c in enumerate(sorted(set(codepoints))))
    sub = struct.pack(">HHLLL", 12, 0, 16 + len(groups), 0, len(set(codepoints))) + groups
    cmap = struct.pack(">HHHHL", 0, 1, 3, 10, 12) + sub
    maxp = struct.pack(">LH", 0x10000, 1200)
    return (struct.pack(">LHHHH", 0x10000, 2, 0, 0, 0) + struct.pack(">4sLLL", b"cmap", 0, 44, len(cmap)) + struct.pack(">4sLLL", b"maxp", 0, 44 + len(cmap), len(maxp)) + cmap + maxp)


def main() -> int:
    work, sdk, evidence = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3])
    project = work / "project"
    (project / "game/fonts").mkdir(parents=True)
    (project / "game/fonts/Gothic.ttf").write_bytes(sfnt(LATIN))
    (project / "game/options.rpy").write_text("define config.save_directory = None\ndefine config.developer = True\n", encoding="utf-8")
    bundled = ROOT / "vntext/fonts/DejaVuSans.ttf"
    digest = hashlib.sha256(bundled.read_bytes()).hexdigest()
    (project / "game/tl/vietnamese").mkdir(parents=True)
    (project / f"game/tl/vietnamese/vntext_font_{digest[:16]}.ttf").write_bytes(bundled.read_bytes())
    (project / "game/tl/vietnamese/vntext.rpy").write_text(prepare_font_support(project, {}, {}, bundled), encoding="utf-8")
    (project / "game/zzz_vntext_vietnamese.rpy").write_text(_render_activation(), encoding="utf-8")
    (project / "game/script.rpy").write_text(SCRIPT, encoding="utf-8")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", RENPY_RENDERER="sw")
    process = subprocess.Popen([str(sdk / "lib/py3-windows-x86_64/python.exe"), "-B", str(sdk / "renpy.py"), str(project)], cwd=sdk, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    try:
        process.wait(timeout=150)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise SystemExit("Ren'Py lifecycle smoke timed out")
    probes = json.loads((project / "lifecycle-out.json").read_text(encoding="utf-8"))
    by_tag = {row[0]: row for row in probes}
    target = "bf06049e.ttf"
    checks = {
        "active_at_start": by_tag["start"][2] == "_VNTextFontMap" and by_tag["start"][3] == target,
        "game_assignment_replaced_the_map": by_tag["game assigned its own config.font_replacement_map"][2] != "_VNTextFontMap",
        "restored_at_next_interaction": by_tag["after the next interaction"][2] == "_VNTextFontMap" and by_tag["after the next interaction"][3] == target,
        "stays_restored": by_tag["second interaction"][2] == "_VNTextFontMap" and by_tag["second interaction"][3] == target,
    }
    result = {"checks": checks, "PASS": all(checks.values()), "probes": probes}
    evidence.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
