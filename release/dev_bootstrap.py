"""Public DEV preflight/build/smoke. Never installs or downloads dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD_RESERVE = 128 * 1024 ** 2
MODEL_FILES = ("model.bin", "config.json", "source.spm", "target.spm", "vocab.json", "tokenizer_config.json")


def run(command, *, cwd=ROOT, env=None):
    try:
        child = subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        return {"command": [str(x) for x in command], "cwd": str(cwd),
                "exit_code": child.returncode, "stdout": child.stdout, "stderr": child.stderr}
    except OSError as error:
        return {"command": [str(x) for x in command], "cwd": str(cwd),
                "exit_code": None, "stdout": "", "stderr": str(error)}


def safe_output(relative):
    """Output is a dedicated DEV child, never an installation/cache/user directory."""
    path = ROOT / relative
    if Path(relative).is_absolute() or len(Path(relative).parts) != 2 or Path(relative).parts[0] != "DEV_RUN":
        raise ValueError("output must be a direct DEV_RUN child")
    if Path(relative).name != "bootstrap-build":
        raise ValueError("only DEV_RUN/bootstrap-build is owned by this tool")
    for part in (ROOT / "DEV_RUN", path):
        if part.is_symlink() or (part.exists() and getattr(part.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"linked output refused: {part}")
    if path.exists() and not (path / ".bootstrap-owner.json").is_file():
        raise ValueError("existing output lacks bootstrap ownership; leave it untouched")
    if path.exists():
        if (path / ".bootstrap-owner.json").is_symlink():
            raise ValueError("linked ownership marker refused")
        marker = json.loads((path / ".bootstrap-owner.json").read_text(encoding="utf-8"))
        if marker != {"owner": "release/dev_bootstrap.py", "purpose": "DEV build and smoke", "root": str(ROOT)}:
            raise ValueError("output ownership mismatch")
    return path


def quota(reserve=0):
    sys.path.insert(0, str(ROOT))
    from tests.tools import cleanup_work_artifacts as cleanup
    inventory = cleanup._project_size_snapshot()
    enough = (inventory["complete"] and inventory["within_limit"] and
              inventory["non_exempt_bytes"] + reserve <= inventory["limit_bytes"])
    return inventory, enough


def discover_python(explicit=None):
    candidates = [explicit] if explicit else [ROOT / ".venv/Scripts/python.exe", ROOT / "DEV_RUN/.venv/Scripts/python.exe",
                                            ROOT / "DEV_RUN/python/python.exe", shutil.which("python"), sys.executable]
    if not explicit and shutil.which("py"):
        launcher = run([shutil.which("py"), "-0p"])
        candidates.extend(re.findall(r"(?m)^.*?([A-Za-z]:\\.*python\.exe)\s*$", launcher["stdout"]))
    checked = []
    for candidate in dict.fromkeys(str(x) for x in candidates if x):
        result = run([candidate, "-B", "-c", "import sys,json; print(json.dumps({'path':sys.executable,'version':list(sys.version_info[:3])}))"])
        checked.append(result)
        if result["exit_code"] == 0:
            try:
                identity = json.loads(result["stdout"])
                if tuple(identity["version"]) >= (3, 11):
                    return identity, checked
            except (ValueError, KeyError, TypeError):
                pass
    return None, checked


def requirements(python):
    # Evaluate requirement specifiers using metadata, not import side effects.
    script = """import importlib.metadata as m,json,sys
from packaging.requirements import Requirement
missing=[]; resolved={}
for line in open(sys.argv[1],encoding='utf-8'):
 line=line.strip()
 if not line or line.startswith('#'): continue
 r=Requirement(line)
 if r.marker and not r.marker.evaluate(): continue
 try:
  v=m.version(r.name); resolved[r.name]=v
  if v not in r.specifier: missing.append(str(r)+' (installed '+v+')')
 except m.PackageNotFoundError: missing.append(str(r))
print(json.dumps({'missing':missing,'resolved':resolved}))
"""
    receipt = run([python, "-B", "-c", script, ROOT / "requirements.txt"])
    if receipt["exit_code"] != 0:
        return {"missing": ["package metadata check failed; see receipt"], "resolved": {}}, receipt
    try:
        return json.loads(receipt["stdout"]), receipt
    except ValueError:
        return {"missing": ["invalid package metadata output"], "resolved": {}}, receipt


def model_inventory(path):
    if not path or not Path(path).is_dir():
        return {"path": str(path) if path else None, "missing": list(MODEL_FILES), "hashes": {},
                "provenance": "UNKNOWN: supply download receipt/revision inventory separately"}
    path = Path(path).resolve()
    missing = [name for name in MODEL_FILES if not (path / name).is_file() or (path / name).stat().st_size == 0]
    hashes = {}
    for name in MODEL_FILES:
        if name not in missing:
            digest = hashlib.sha256()
            with (path / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            hashes[name] = digest.hexdigest()
    return {"path": str(path), "missing": missing, "hashes": hashes,
            "provenance": "UNKNOWN: hashes prove current bytes, not model revision/license"}


def smoke_success(report):
    """Require the real five-step protocol, not merely process exit zero."""
    if report["schema"] != 1 or report["ok"] is not True or report["exit_code"] != 0 or report["cleanup_error"] is not None:
        return False
    steps = report["steps"]
    if [step["step"] for step in steps] != ["cancel", "extract", "translate", "patch", "crash"]:
        return False
    for step in steps:
        if step["exit_code"] != 0 or step["exception"] is not None:
            return False
        if step["step"] in ("extract", "translate", "patch"):
            completions = [event for event in step["events"] if event["type"] == "complete" and event["id"] == "smoke-" + step["step"]]
            if len(completions) != 1 or completions[0]["ok"] is not True:
                return False
    return True


def preflight(python=None, dotnet=None, model=None, gate="dev", reserve=0):
    receipts, missing = [], []
    identity, checks = discover_python(python)
    receipts.extend(checks)
    packages = None
    if not identity:
        missing.append({"gate": "DEV/smoke", "item": "Python 3.11+", "source": "https://www.python.org/downloads/windows/", "permission": "install runtime if absent"})
    else:
        packages, receipt = requirements(identity["path"])
        receipts.append(receipt)
        check = run([identity["path"], "-B", "-m", "pip", "check"])
        receipts.append(check)
        if packages["missing"] or check["exit_code"] != 0:
            missing.append({"gate": "DEV/smoke", "item": packages["missing"] or "pip check failed", "source": "https://pypi.org", "permission": "install requirements/dependencies into chosen environment"})
    dotnet = str(dotnet or shutil.which("dotnet") or "dotnet")
    sdk = run([dotnet, "--list-sdks"])
    runtimes = run([dotnet, "--list-runtimes"])
    receipts.extend([sdk, runtimes])
    local10 = ROOT / "DEV_RUN/dotnet-sdk-10/dotnet.exe"
    local_sdk = run([local10, "--list-sdks"]) if local10.is_file() else None
    if local_sdk:
        receipts.append(local_sdk)
    sdk8 = re.findall(r"(?m)^8\.\S+ \[(.+)\]", sdk["stdout"])
    sdk10 = re.findall(r"(?m)^10\.\S+ \[(.+)\]", sdk["stdout"] + (local_sdk["stdout"] if local_sdk else ""))
    desktop_refs = []
    for sdk_root in sdk8:
        desktop_refs.extend(str(x) for x in (Path(sdk_root).parent / "packs/Microsoft.WindowsDesktop.App.Ref").glob("8.*"))
    if sdk["exit_code"] != 0 or not sdk8 or not desktop_refs:
        missing.append({"gate": "DEV/smoke", "item": "SDK 8 + WindowsDesktop targeting pack", "source": "https://dotnet.microsoft.com/download/dotnet/8.0", "permission": "install official SDK/pack if absent"})
    if not re.search(r"(?m)^Microsoft.WindowsDesktop.App 8\.", runtimes["stdout"]):
        missing.append({"gate": "DEV/smoke", "item": "WPF runtime 8", "source": "https://dotnet.microsoft.com/download/dotnet/8.0", "permission": "install official desktop runtime if absent"})
    model_info = model_inventory(model or os.environ.get("VNTEXT_CT2_MODEL"))
    if gate == "smoke" and model_info["missing"]:
        missing.append({"gate": "smoke", "item": model_info["missing"], "source": "vntext/mt_ct2_constants.py", "permission": "download pinned model if absent"})
    git = run([shutil.which("git") or "git", "rev-parse", "HEAD"])
    receipts.append(git)
    if git["exit_code"] != 0:
        missing.append({"gate": "DEV", "item": "Git/source identity", "permission": "provide clean public checkout"})
    inventory, enough = quota(reserve)
    if not enough:
        missing.append({"gate": "DEV/smoke", "item": "complete whole-project quota + reserved bytes", "permission": "resolve exact owned artifacts; no automatic deletion"})
    return {"source_sha": git["stdout"].strip(), "python": identity, "packages": packages,
            "dotnet": dotnet, "desktop_refs": desktop_refs, "model": model_info,
            "quota": inventory, "reserved_bytes": reserve, "missing": missing, "receipts": receipts,
            "optional_release": {"sdk10_visible": bool(sdk10), "acceptance": "NOT RUN",
                                 "requirements": "SDK10 pinned packs, Program Files runtime8, csc, portable Python3.12, Pillow, model provenance, baseline and epoch; see docs/DEVELOPMENT.md"},
            "dependency_provenance": "Observed executable paths/versions and installed metadata only; retain official download receipts separately",
            "nuget": {"source": "https://api.nuget.org/v3/index.json", "readiness": "UNKNOWN until restore/build succeeds"}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("check", "build", "smoke"), default="check")
    parser.add_argument("--gate", choices=("dev", "smoke"), default="dev")
    parser.add_argument("--python")
    parser.add_argument("--dotnet")
    parser.add_argument("--model")
    parser.add_argument("--shared-root", help="Existing dependency/cache checkout; explicit, never copied")
    args = parser.parse_args(argv)
    result = {}
    try:
        shared = Path(args.shared_root).resolve() if args.shared_root else ROOT
        if args.action != "check":
            output = safe_output("DEV_RUN/bootstrap-build")
            # Shared resources remain within the containing DEV checkout.
            inventory, _ = quota()
            if not shared.is_relative_to(Path(inventory["root"]).resolve()):
                raise ValueError("shared-root must stay inside containing DEV checkout")
        result = preflight(args.python, args.dotnet, args.model,
                           "smoke" if args.action == "smoke" else args.gate,
                           BUILD_RESERVE if args.action != "check" else 0)
        code = 2 if result["missing"] else 0
        if args.action != "check" and not code:
            output.mkdir(parents=True, exist_ok=True)
            marker = output / ".bootstrap-owner.json"
            if not marker.exists():
                marker.write_text(json.dumps({"owner": "release/dev_bootstrap.py", "purpose": "DEV build and smoke", "root": str(ROOT)}), encoding="utf-8")
            cache = shared / "DEV_RUN/cache"
            cache.mkdir(parents=True, exist_ok=True)
            nuget = output / "NuGet.Config"
            # Offline by default: installed packs/global cache, no network restore.
            import xml.sax.saxutils
            source = xml.sax.saxutils.escape(str(cache / "nuget"), {'"': '&quot;'})
            config = f'<configuration><packageSources><clear/><add key="local-cache" value="{source}"/></packageSources></configuration>'
            if not nuget.exists():
                nuget.write_text(config, encoding="utf-8")
            elif nuget.read_text(encoding="utf-8") != config:
                raise ValueError("owned NuGet.Config changed; refuse overwrite")
            env = os.environ.copy()
            env.update(NUGET_PACKAGES=str(cache / "nuget"), DOTNET_CLI_HOME=str(cache / "dotnet-home"),
                       APPDATA=str(cache / "appdata"), LOCALAPPDATA=str(cache / "localappdata"),
                       DOTNET_GENERATE_ASPNET_CERTIFICATE="false", VNTEXT_WORKER_CWD=str(ROOT),
                       VNTEXT_WORKER_PYTHON=result["python"]["path"], VNTEXT_CT2_NO_DOWNLOAD="1",
                       VNTEXT_DATA_ROOT=str(output / "data"))
            if result["model"]["path"]:
                env["VNTEXT_CT2_MODEL"] = result["model"]["path"]
            build = run([result["dotnet"], "build", ROOT / "wpf_app/VNText.Studio.App/VNText.Studio.App.csproj",
                         "-c", "Debug", "-o", output, f"-p:RestoreConfigFile={nuget}"], env=env)
            result["receipts"].append(build)
            code = build["exit_code"] if build["exit_code"] is not None else 1
            if not code and args.action == "smoke":
                report_path = output / "smoke.json"
                if report_path.exists():
                    if report_path.is_symlink():
                        raise ValueError("linked smoke report refused")
                    report_path.unlink()  # Exact owned prior report; no stale PASS evidence.
                smoke = run([output / "VNText.Studio.App.exe", "--smoke-worker", "--report", output / "smoke.json"], env=env)
                result["receipts"].append(smoke)
                code = smoke["exit_code"] if smoke["exit_code"] is not None else 1
                result["smoke_report"] = json.loads((output / "smoke.json").read_text(encoding="utf-8"))
                if not code and not smoke_success(result["smoke_report"]):
                    code = 1
            result["quota_after"], enough = quota()
            if not enough:
                result["cleanup_status"] = "REVIEW_REQUIRED: quota exceeded/incomplete"
                code = code or 2
        result["exit_code"] = code
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["exit_code"] = 1
    # Windows redirected stdout can be cp1252; JSON escapes preserve exact Unicode.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
