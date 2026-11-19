"""Mono/TMP runtime font adapter for Unity players: guards, deterministic payload and exact re-verification.

The adapter (``wpf_app/VNText.UnityTmpAdapter``) registers ONE hash-bound dynamic TextMeshPro font as the first *global* TMP fallback while the
player runs.  It edits no game asset: the staged payload is the adapter assembly, a three-line config, the font (+ licence for the bundled font) and
the two small registration JSON files that make the player load the assembly.  Uninstall restores those two files byte for byte and removes the rest.

Scope (not generalised): Mono scripting backend, Unity engine versions in ``VALIDATED_ENGINES`` only, TextMeshPro text only (legacy ``UnityEngine.UI.Text``
and per-component font swaps are not covered), runtime acceptance is a separate native verdict.  IL2CPP builds, unknown engine versions, a missing TMP
assembly, an unexpected registration schema or an already present adapter are refused with the exact reason; nothing is guessed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from vntext.patch_font_preflight import inspect_font, required_characters

ADAPTER_ASSEMBLY = "VNTextTmpFonts"
ADAPTER_FILE = ADAPTER_ASSEMBLY + ".dll"
CONFIG_FILE = "vntext_tmp_font.cfg"
FONT_PREFIX = "vntext_tmp_font_"
VALIDATED_ENGINES = ("2022.3.16f1",)        # the only Unity version with a fixture + static probe; extend only with new evidence
REQUIRED_MANAGED = ("Unity.TextMeshPro.dll", "UnityEngine.CoreModule.dll", "UnityEngine.TextRenderingModule.dll", "mscorlib.dll", "netstandard.dll")
TMP_API_NAMES = (b"CreateFontAsset", b"TryAddCharacters", b"fallbackFontAssets")
ADAPTER_REQUIRED_NAMES = (b"VNTextTmpFonts", b"Startup", b"Initialize", b"RuntimeInitializeOnLoadMethodAttribute", b"TMP_FontAsset", b"TMP_Settings")
ADAPTER_ALLOWED_REFERENCES = {b"netstandard", b"UnityEngine.CoreModule", b"UnityEngine.TextRenderingModule", b"Unity.TextMeshPro"}
ADAPTER_FORBIDDEN_NAMES = (b"System.Net", b"System.Diagnostics.Process", b"Process", b"UnityEngine.Networking", b"UnityWebRequest", b"Assembly.Load",
                           b"LoadFrom", b"Assembly", b"Delete", b"Move", b"WriteAll", b"AppendAll", b"FileStream", b"Socket", b"WebClient")
MAX_JSON_BYTES = 1024 * 1024
MAX_ADAPTER_BYTES = 256 * 1024
_ENGINE = re.compile(rb"(?<![0-9.])(\d{4}\.\d+\.\d+[abfp]\d+)(?![0-9a-z])")
_REGISTRATION_KEYS = ("assemblyName", "nameSpace", "className", "methodName", "loadTypes", "isUnityClass")


class UnityTmpAdapterError(ValueError):
    pass


def bundled_adapter_path() -> Path:
    """The packaged adapter assembly (``VNTEXT_UNITY_TMP_ADAPTER_DLL`` selects another build for QA; it is validated the same way)."""
    import os
    override = os.environ.get("VNTEXT_UNITY_TMP_ADAPTER_DLL")
    path = Path(override) if override else Path(__file__).resolve().parent / "unity_adapter" / ADAPTER_FILE
    if not path.is_file() or path.is_symlink():
        raise UnityTmpAdapterError("the Unity TMP adapter assembly is not packaged with this build")
    return path


def _sha256(path_or_bytes) -> str:
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    return hashlib.sha256(data).hexdigest()


def _regular_file(path: Path, limit: int | None = None) -> Path:
    if path.is_symlink() or not path.is_file() or (limit is not None and path.stat().st_size > limit):
        raise UnityTmpAdapterError(f"missing, linked or oversized file: {path.name}")
    return path


def _engine_version(root: Path, data_dir: Path) -> str:
    for source in (root / data_dir.name / "data.unity3d", data_dir / "data.unity3d", data_dir / "globalgamemanagers"):
        if source.is_file() and not source.is_symlink():
            with source.open("rb") as stream:
                head = stream.read(512)
            found = {m.decode("ascii") for m in _ENGINE.findall(head)}
            if len(found) != 1:
                raise UnityTmpAdapterError(f"engine version in {source.name} is not exactly one recognisable value")
            return found.pop()
    raise UnityTmpAdapterError("no data.unity3d or globalgamemanagers to read the Unity engine version from")


def _registration_documents(data_dir: Path) -> tuple[dict, dict]:
    startup = json.loads(_regular_file(data_dir / "RuntimeInitializeOnLoads.json", MAX_JSON_BYTES).read_text(encoding="utf-8"))
    assemblies = json.loads(_regular_file(data_dir / "ScriptingAssemblies.json", MAX_JSON_BYTES).read_text(encoding="utf-8"))
    root = startup.get("root") if isinstance(startup, dict) else None
    names, types = (assemblies.get("names"), assemblies.get("types")) if isinstance(assemblies, dict) else (None, None)
    if not isinstance(root, list) or set(startup) != {"root"} or any(not isinstance(item, dict) or tuple(item) != _REGISTRATION_KEYS for item in root):
        raise UnityTmpAdapterError("RuntimeInitializeOnLoads.json has an unrecognised schema")
    if (not isinstance(names, list) or not isinstance(types, list) or len(names) != len(types) or set(assemblies) != {"names", "types"}
            or any(not isinstance(n, str) for n in names) or any(type(t) is not int for t in types)):
        raise UnityTmpAdapterError("ScriptingAssemblies.json has an unrecognised schema")
    return startup, assemblies


def inspect_runtime_support(game_root) -> dict:
    """Static, read-only eligibility.  ``supported`` is True only when every guard passes; otherwise ``reasons`` lists each exact refusal."""
    root = Path(game_root).resolve()
    reasons: list[str] = []
    result: dict = {"supported": False, "reasons": reasons, "engine_version": "", "data_dir": "", "executable": "", "game_checks": []}
    if not root.is_dir():
        reasons.append("game folder not found")
        return result
    data_dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.casefold().endswith("_data"))
    if len(data_dirs) != 1:
        reasons.append(f"expected exactly one *_Data folder, found {len(data_dirs)}")
        return result
    data_dir = data_dirs[0]
    result["data_dir"] = data_dir.name
    executables = sorted(p.name for p in root.glob("*.exe") if p.stem + "_Data" == data_dir.name)
    result["executable"] = executables[0] if len(executables) == 1 else ""
    if not result["executable"]:
        reasons.append("the player executable matching the *_Data folder was not found")
    if (root / "GameAssembly.dll").exists() or (data_dir / "il2cpp_data").exists():
        reasons.append("IL2CPP scripting backend: a managed adapter cannot be loaded")
    if not (data_dir / "Managed").is_dir() or not (root / "MonoBleedingEdge").is_dir():
        reasons.append("Mono scripting backend not detected (Managed/ or MonoBleedingEdge/ missing)")
    try:
        engine = _engine_version(root, data_dir)
        result["engine_version"] = engine
        if engine not in VALIDATED_ENGINES:
            reasons.append(f"Unity {engine} is not a validated engine version ({', '.join(VALIDATED_ENGINES)})")
    except UnityTmpAdapterError as exc:
        reasons.append(str(exc))
    managed = data_dir / "Managed"
    checks = []
    for name in REQUIRED_MANAGED:
        try:
            data = _regular_file(managed / name).read_bytes()
        except (UnityTmpAdapterError, OSError):
            reasons.append(f"required assembly missing: Managed/{name}")
            continue
        if name == "Unity.TextMeshPro.dll" and any(api not in data for api in TMP_API_NAMES):
            reasons.append("Unity.TextMeshPro.dll does not expose the APIs the adapter uses")
        checks.append({"path": f"{data_dir.name}/Managed/{name}", "sha256": _sha256(data)})
    try:
        startup, assemblies = _registration_documents(data_dir)
        if "Assembly-CSharp.dll" not in assemblies["names"]:
            reasons.append("ScriptingAssemblies.json lists no Assembly-CSharp.dll to copy the user-assembly type from")
        if any(item["assemblyName"] == ADAPTER_ASSEMBLY for item in startup["root"]) or ADAPTER_FILE in assemblies["names"]:
            reasons.append("the adapter is already registered")
        for name in ("RuntimeInitializeOnLoads.json", "ScriptingAssemblies.json"):
            checks.append({"path": f"{data_dir.name}/{name}", "sha256": _sha256(data_dir / name)})
    except (UnityTmpAdapterError, ValueError, OSError) as exc:
        reasons.append(str(exc))
    leftovers = [p.name for p in (list(data_dir.glob(FONT_PREFIX + "*")) + [data_dir / CONFIG_FILE, managed / ADAPTER_FILE]) if p.exists()]
    if leftovers:
        reasons.append("adapter files already present: " + ", ".join(sorted(leftovers)))
    result["game_checks"] = checks
    result["supported"] = not reasons
    return result


def inspect_adapter_binary(data: bytes) -> str:
    """Cheap structural allow-list for the adapter assembly (managed PE, expected names, allowed references, no I/O or network primitives)."""
    if not data.startswith(b"MZ") or b"BSJB" not in data or len(data) > MAX_ADAPTER_BYTES:
        raise UnityTmpAdapterError("adapter is not a bounded managed assembly")
    for name in ADAPTER_REQUIRED_NAMES:
        if name not in data:
            raise UnityTmpAdapterError("adapter assembly lacks " + name.decode())
    for name in ADAPTER_FORBIDDEN_NAMES:
        if name in data:
            raise UnityTmpAdapterError("adapter assembly references a forbidden API: " + name.decode())
    for found in re.findall(rb"UnityEngine\.[A-Za-z]+Module|Unity\.TextMeshPro", data):
        if found not in ADAPTER_ALLOWED_REFERENCES:
            raise UnityTmpAdapterError("adapter references an unexpected Unity assembly: " + found.decode())
    return _sha256(data)


def _compact(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _expected_payload(game_root: Path, support: dict, font_bytes: bytes, characters: str, adapter: bytes, licence: bytes | None) -> dict[str, bytes]:
    data_dir = game_root / support["data_dir"]
    startup, assemblies = _registration_documents(data_dir)
    startup["root"].append({"assemblyName": ADAPTER_ASSEMBLY, "nameSpace": ADAPTER_ASSEMBLY, "className": "Startup", "methodName": "Initialize",
                            "loadTypes": 1, "isUnityClass": False})
    assemblies["types"].append(assemblies["types"][assemblies["names"].index("Assembly-CSharp.dll")])
    assemblies["names"].append(ADAPTER_FILE)
    digest = hashlib.sha256(font_bytes).hexdigest()
    font_name = f"{FONT_PREFIX}{digest[:16]}.ttf"
    prefix = support["data_dir"] + "/"
    files = {
        prefix + "Managed/" + ADAPTER_FILE: adapter,
        prefix + CONFIG_FILE: f"{font_name}\n{digest}\n{characters}\n".encode("utf-8"),
        prefix + font_name: font_bytes,
        prefix + "RuntimeInitializeOnLoads.json": _compact(startup),
        prefix + "ScriptingAssemblies.json": _compact(assemblies),
    }
    if licence is not None:
        files[prefix + font_name.replace(".ttf", ".license.txt")] = licence
    return files


def stage_adapter_payload(game_root, output_dir, font_path, translations, adapter_dll) -> dict:
    """Stage the adapter payload under ``<output>/COPY_TO_GAME_ROOT`` and write ``unity_tmp_adapter.json``; refuses on any failed guard."""
    root, output = Path(game_root).resolve(), Path(output_dir).resolve()
    if root == output or root in output.parents or output in root.parents:
        raise UnityTmpAdapterError("adapter output must be separate from the game")
    support = inspect_runtime_support(root)
    if not support["supported"]:
        raise UnityTmpAdapterError("Unity TMP runtime adapter refused: " + "; ".join(support["reasons"]))
    characters = "".join(chr(code) for code in required_characters(translations))
    font = Path(font_path)
    report = inspect_font(font, [ord(c) for c in characters])
    if report["missing"]:
        raise UnityTmpAdapterError("selected font lacks translated glyphs: " + ", ".join(str(code) for code in report["missing"][:24]))
    if font.suffix.lower() != ".ttf":
        raise UnityTmpAdapterError("the adapter loads TrueType (.ttf) fonts only")
    font_bytes = font.read_bytes()
    adapter = _regular_file(Path(adapter_dll), MAX_ADAPTER_BYTES).read_bytes()
    adapter_sha = inspect_adapter_binary(adapter)
    bundled = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"
    licence = bundled.with_suffix(".txt").read_bytes() if bundled.is_file() and font_bytes == bundled.read_bytes() else None
    files = _expected_payload(root, support, font_bytes, characters, adapter, licence)
    payload_root = output / "COPY_TO_GAME_ROOT"
    for relative, data in files.items():
        target = payload_root / relative
        if target.exists():
            raise UnityTmpAdapterError("payload target already exists: " + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    evidence = {
        "schema": 1, "adapter": ADAPTER_ASSEMBLY, "engine_version": support["engine_version"], "data_dir": support["data_dir"],
        "executable": support["executable"], "game_checks": support["game_checks"], "adapter_sha256": adapter_sha,
        "font_sha256": report["sha256"], "characters": len(characters), "glyph_status": "PASS",
        "mapping_status": "TMP_GLOBAL_FALLBACK_ADAPTER", "runtime_status": "NOT_PROVEN",
        "payload": {relative: _sha256(data) for relative, data in sorted(files.items())},
        "scope": "TextMeshPro text only; legacy UI Text and per-component font swaps are not covered; runtime acceptance is a separate native verdict.",
    }
    (output / "unity_tmp_adapter.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def verify_staged_payload(game_root, output_dir) -> dict:
    """Re-derive the payload from the *current* game files and compare byte for byte (detects a changed game, tampered or stray payload)."""
    root, output = Path(game_root).resolve(), Path(output_dir).resolve()
    evidence = json.loads(_regular_file(output / "unity_tmp_adapter.json", MAX_JSON_BYTES).read_text(encoding="utf-8"))
    payload_root = output / "COPY_TO_GAME_ROOT"
    staged = {p.relative_to(payload_root).as_posix(): p for p in payload_root.rglob("*") if p.is_file()}
    prefix = evidence["data_dir"] + "/"
    # Other payload files (the text patch) may share the folder; anything that looks like adapter material but is not in the evidence may not.
    stray = sorted(name for name in set(staged) - set(evidence["payload"])
                   if name.startswith(prefix + FONT_PREFIX) or name in (prefix + CONFIG_FILE, prefix + "Managed/" + ADAPTER_FILE))
    if stray or not set(evidence["payload"]) <= set(staged):
        raise UnityTmpAdapterError("staged payload differs from its evidence: " + ", ".join(stray or ["missing files"]))
    for relative, digest in evidence["payload"].items():
        if staged[relative].is_symlink() or _sha256(staged[relative]) != digest:
            raise UnityTmpAdapterError("staged payload bytes changed: " + relative)
    support = inspect_runtime_support(root)
    if not support["supported"] or support["game_checks"] != evidence["game_checks"]:
        raise UnityTmpAdapterError("the game no longer matches the adapter evidence: " + "; ".join(support["reasons"] or ["game checks changed"]))
    prefix = support["data_dir"] + "/"
    font_names = [n for n in evidence["payload"] if n.startswith(prefix + FONT_PREFIX) and n.endswith(".ttf")]
    if len(font_names) != 1:
        raise UnityTmpAdapterError("payload must contain exactly one adapter font")
    font_bytes = staged[font_names[0]].read_bytes()
    config = staged[prefix + CONFIG_FILE].read_text(encoding="utf-8").split("\n")
    licence_name = font_names[0].replace(".ttf", ".license.txt")
    licence = staged[licence_name].read_bytes() if licence_name in staged else None
    expected = _expected_payload(root, support, font_bytes, config[2], staged[prefix + "Managed/" + ADAPTER_FILE].read_bytes(), licence)
    if {k: _sha256(v) for k, v in expected.items()} != evidence["payload"]:
        raise UnityTmpAdapterError("staged payload is not the deterministic adapter payload for this game")
    if inspect_adapter_binary(expected[prefix + "Managed/" + ADAPTER_FILE]) != evidence["adapter_sha256"]:
        raise UnityTmpAdapterError("adapter binary changed")
    return evidence
