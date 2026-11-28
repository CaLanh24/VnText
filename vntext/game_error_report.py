"""Report an error of the PATCHED game (not of VNText): read Ren'Py's traceback.txt, find which line of the generated translation file caused it, and offer to
take that line out again.  Everything that leaves the machine is anonymous: exception kind, line numbers and a hash of the unit id - never a game name,
a path or a sentence."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from vntext.renpy_markup import overlay_problems

OVERLAY_RELATIVE = "game/tl/vietnamese/vntext.rpy"
TRACEBACK_NAMES = ("traceback.txt",)
_FRAME = re.compile(r'File "([^"]+)", line (\d+)')
_EXCEPTION = re.compile(r"^(?P<kind>[A-Za-z_][\w.]*(?:Error|Exception|Warning)?)\s*:\s*(?P<message>.*)$")
_VERSION = re.compile(r"Ren'Py\s+(\d+\.\d+\.\d+(?:\.\d+)?)")
_QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')


def find_traceback(game_root: str | Path) -> Path | None:
    root = Path(game_root)
    for name in TRACEBACK_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _short_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def classify_exception(message: str) -> str:
    low = message.lower()
    if "open format operation" in low:
        return "markup_open_bracket"
    if "text tag" in low or "close text tag" in low:
        return "markup_text_tag"
    if "keyerror" in low or "not defined" in low or "nameerror" in low:
        return "name_not_defined"
    if "font" in low:
        return "font"
    if "syntax" in low or "parse" in low:
        return "script_syntax"
    return "other"


def parse_traceback(text: str) -> dict:
    """Anonymous facts of a Ren'Py traceback.txt: exception kind + class, Ren'Py version, game/ frames (file *kind* and line) - no message text."""
    lines = text.splitlines()
    frames = []
    exception_kind = ""
    exception_message = ""
    in_game_code = False
    for line in lines:
        if line.strip().startswith("While running game code"):
            in_game_code = True
            continue
        if in_game_code and line.startswith("  File"):
            m = _FRAME.search(line)
            if m:
                frames.append({"file": m.group(1).replace("\\", "/"), "line": int(m.group(2))})
            continue
        if in_game_code and line and not line.startswith(" "):
            m = _EXCEPTION.match(line)
            if m:
                exception_kind, exception_message = m.group("kind"), m.group("message")
            in_game_code = False
    version = _VERSION.search(text)
    own = [f for f in frames if f["file"].replace("\\", "/").endswith(OVERLAY_RELATIVE.split("game/", 1)[1])]
    return {
        "exception_class": exception_kind,
        "kind": classify_exception(exception_message or exception_kind),
        "renpy_version": version.group(1) if version else "",
        "frames": [{"file_kind": "vntext_overlay" if f in own else ("game_script" if f["file"].startswith("game/") else "engine"), "line": f["line"]} for f in frames],
        "overlay_lines": [f["line"] for f in own],
        "_message": exception_message,       # private: used to find the sentence, never written to the report
    }


def _blocks(overlay_text: str):
    """Yield (start_line, end_line, kind, id) of every translate block of the overlay (1-based, inclusive)."""
    lines = overlay_text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("translate ")]
    for pos, start in enumerate(starts):
        end = (starts[pos + 1] - 1) if pos + 1 < len(starts) else len(lines) - 1
        while end > start and not lines[end].strip():
            end -= 1
        head = lines[start].split()
        ident = head[2].rstrip(":") if len(head) >= 3 else ""
        yield start + 1, end + 1, ("strings" if ident == "strings" else "dialogue"), ident


def locate_units(game_root: str | Path, lines_of_interest: list[int], message: str = "") -> list[dict]:
    """Which overlay units the traceback points at: by frame line first, then by the sentence the exception quotes."""
    overlay = Path(game_root) / OVERLAY_RELATIVE
    try:
        text = overlay.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = text.splitlines()
    wanted = set(int(n) for n in lines_of_interest)
    quoted = ""
    m = re.search(r"String '(.*)' ends with", message or "", re.S)
    if m:
        quoted = m.group(1)
    for number, row in enumerate(rows, 1):
        stripped = row.strip()
        if quoted and stripped and not stripped.startswith(("#", "old ")):
            lit = _QUOTED.search(stripped[4:] if stripped.startswith("new ") else stripped)
            if lit:
                try:
                    decoded = json.loads(lit.group(0))
                except ValueError:
                    continue
                if decoded == quoted or repr(decoded)[1:-1] == quoted:
                    wanted.add(number)
    found = []
    for start, end, kind, ident in _blocks(text):
        hit = sorted(n for n in wanted if start <= n <= end)
        if hit and kind == "strings":
            # One old/new pair per hit: dropping the whole "strings" block would take every other translated string with it.
            for n in hit:
                begin = n
                while begin > start and not rows[begin - 1].strip().startswith("old "):
                    begin -= 1
                found.append({"block": [begin, n], "unit_type": "strings", "native_id": "", "id_hash": _short_id(f"strings:{begin}"), "lines": [n]})
            continue
        if hit:
            found.append({"block": [start, end], "unit_type": kind, "native_id": ident if kind == "dialogue" else "", "id_hash": _short_id(ident or f"{kind}:{start}"), "lines": hit})
    return found


def scan_game(game_root: str | Path, manifest: str | Path | None = None) -> dict:
    """Traceback (if any) + every overlay line that Ren'Py cannot display.  Returns a plain-Vietnamese ``lines`` preview and the anonymous ``report``."""
    root = Path(game_root)
    tb_path = find_traceback(root)
    traceback = parse_traceback(tb_path.read_text(encoding="utf-8", errors="replace")) if tb_path else {}
    message = traceback.pop("_message", "") if traceback else ""
    overlay = root / OVERLAY_RELATIVE
    broken: list[tuple[int, str]] = []
    if overlay.is_file():
        try:
            broken = overlay_problems(overlay.read_text(encoding="utf-8"))
        except OSError:
            broken = []
    wanted_lines = list(traceback.get("overlay_lines") or []) + [n for n, _ in broken]
    units = locate_units(root, wanted_lines, message) if overlay.is_file() else []
    keys: dict[str, str] = {}
    if manifest and Path(manifest).is_file():
        try:
            for entry in json.loads(Path(manifest).read_text(encoding="utf-8-sig")).get("entries", []):
                nid = str((entry.get("locator") or {}).get("native_id") or "")
                if nid:
                    keys[nid] = str(entry.get("key") or "")
        except (OSError, ValueError):
            pass
    for unit in units:
        key = keys.get(unit["native_id"], "")
        unit["key"] = key
        unit["key_hash"] = _short_id(key) if key else ""
    report = {
        "schema": 1,
        "traceback_found": bool(tb_path),
        "exception_class": traceback.get("exception_class", ""),
        "kind": traceback.get("kind", ""),
        "renpy_version": traceback.get("renpy_version", ""),
        "frames": traceback.get("frames", []),
        "broken_overlay_lines": [n for n, _ in broken],
        "units": [{k: v for k, v in u.items() if k not in ("native_id", "key")} for u in units],
    }
    lines: list[str] = []
    if not tb_path and not broken:
        lines.append("Không thấy tệp traceback.txt trong thư mục game, và tệp bản dịch trong game không có dòng nào hỏng.")
    if tb_path:
        words = {"markup_open_bracket": "dấu [ ] trong một câu bản dịch không đóng (game dừng khi hiện câu đó)",
                 "markup_text_tag": "thẻ { } trong một câu bản dịch bị hỏng",
                 "name_not_defined": "game dùng một tên/biến chưa có", "font": "lỗi phông chữ", "script_syntax": "lỗi cú pháp trong tệp script"}.get(report["kind"], "lỗi khác của game")
        lines.append(f"Game báo lỗi: {words}." + (f" Ren'Py {report['renpy_version']}." if report["renpy_version"] else ""))
        if traceback.get("overlay_lines"):
            lines.append("Lỗi nằm trong tệp bản dịch do VNText tạo (game/tl/vietnamese/vntext.rpy).")
    if broken:
        lines.append(f"Tệp bản dịch trong game có {len(broken)} dòng game không đọc được: " + "; ".join(f"dòng {n}" for n, _ in broken[:12]) + (" …" if len(broken) > 12 else ""))
    for unit in units:
        where = "câu thoại" if unit["unit_type"] == "dialogue" else "chuỗi giao diện"
        lines.append(f"  - {where} ở dòng {unit['block'][0]}–{unit['block'][1]} của tệp bản dịch (mã {unit['id_hash']})" + (f", dòng {unit['key']} trong bản dịch của bạn" if unit.get("key") else ""))
    return {"report": report, "lines": lines, "units": units, "revertable": bool(units) and overlay.is_file()}


def revert_units(game_root: str | Path, blocks: list[list[int]]) -> dict:
    """Take the given translate blocks (line ranges) out of the generated file; the game then shows the original sentence there.  A backup is kept next to it."""
    overlay = Path(game_root) / OVERLAY_RELATIVE
    text = overlay.read_text(encoding="utf-8")
    rows = text.splitlines(keepends=True)
    drop: set[int] = set()
    for start, end in blocks:
        drop.update(range(int(start) - 1, int(end)))
    kept = [row for i, row in enumerate(rows) if i not in drop]
    # A "translate vietnamese strings:" header with no old/new left would be an empty block (a Ren'Py parse error): drop it too.
    cleaned: list[str] = []
    for i, row in enumerate(kept):
        if row.startswith("translate ") and row.rstrip().endswith("strings:"):
            rest = kept[i + 1:]
            has_body = False
            for follower in rest:
                if follower.startswith("translate "):
                    break
                if follower.strip().startswith(("old ", "new ")):
                    has_body = True
                    break
            if not has_body:
                continue
        cleaned.append(row)
    backup = overlay.with_name(f"vntext.rpy.vntext-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(overlay, backup)
    overlay.write_text("".join(cleaned), encoding="utf-8")
    after = overlay_problems(overlay.read_text(encoding="utf-8"))
    return {"removed_lines": len(rows) - len(cleaned), "backup": str(backup), "remaining_problems": [n for n, _ in after]}
