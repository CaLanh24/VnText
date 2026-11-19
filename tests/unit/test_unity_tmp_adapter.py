from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext import unity_tmp_adapter as adapter
from vntext.patch_output import write_patch_manifest

WORK = work_temp_dir("unity-tmp-adapter-tests")
REPO = Path(__file__).resolve().parents[2]
FONT = REPO / "vntext/fonts/DejaVuSans.ttf"
TEXT = ["Xin chào, Đặng Nguyễn Ắ Ặ Ộ Ở Ữ Ự"]
STARTUP = {"root": [{"assemblyName": "Game", "nameSpace": "Game", "className": "Boot", "methodName": "Init", "loadTypes": 1, "isUnityClass": False}]}
ASSEMBLIES = {"names": ["UnityEngine.dll", "Assembly-CSharp.dll"], "types": [0, 16]}


def adapter_binary(extra: bytes = b"") -> bytes:
    names = b"\0".join([b"VNTextTmpFonts", b"Startup", b"Initialize", b"RuntimeInitializeOnLoadMethodAttribute", b"TMP_FontAsset", b"TMP_Settings",
                        b"netstandard", b"UnityEngine.CoreModule", b"UnityEngine.TextRenderingModule", b"Unity.TextMeshPro"])
    return b"MZ" + b"\0" * 62 + b"BSJB" + names + extra


class UnityTmpAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_tempdir = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior_tempdir

    def _game(self, base: Path, *, engine=b"2022.3.16f1", il2cpp=False, tmp_api=True) -> Path:
        game = base / "game"
        data = game / "TEST_Data"
        (data / "Managed").mkdir(parents=True)
        (game / "MonoBleedingEdge").mkdir()
        (game / "TEST.exe").write_bytes(b"MZ player")
        (data / "data.unity3d").write_bytes(b"UnityFS\0\0\0\0\x08" + b"5.x.x\0" + engine + b"\0" + b"\0" * 64)
        for name in adapter.REQUIRED_MANAGED + ("Assembly-CSharp.dll",):
            body = b"MZ assembly " + name.encode()
            if name == "Unity.TextMeshPro.dll" and tmp_api:
                body += b" ".join(adapter.TMP_API_NAMES)
            (data / "Managed" / name).write_bytes(body)
        (data / "RuntimeInitializeOnLoads.json").write_text(json.dumps(STARTUP, separators=(",", ":")), encoding="utf-8")
        (data / "ScriptingAssemblies.json").write_text(json.dumps(ASSEMBLIES, separators=(",", ":")), encoding="utf-8")
        if il2cpp:
            (game / "GameAssembly.dll").write_bytes(b"MZ")
        return game

    def _dll(self, base: Path, data: bytes | None = None) -> Path:
        path = base / "VNTextTmpFonts.dll"
        path.write_bytes(adapter_binary() if data is None else data)
        return path

    def _snapshot(self, game: Path) -> dict[str, bytes]:
        return {p.relative_to(game).as_posix(): p.read_bytes() for p in game.rglob("*") if p.is_file()}

    def test_supported_layout_passes_every_guard_and_stays_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            game = self._game(Path(temp))
            before = self._snapshot(game)
            result = adapter.inspect_runtime_support(game)
            self.assertTrue(result["supported"], result["reasons"])
            self.assertEqual((result["engine_version"], result["data_dir"], result["executable"]), ("2022.3.16f1", "TEST_Data", "TEST.exe"))
            self.assertEqual(self._snapshot(game), before)

    def test_unsupported_layouts_are_refused_with_the_exact_reason(self):
        cases = {
            "IL2CPP": (dict(il2cpp=True), "IL2CPP"),
            "engine version": (dict(engine=b"2021.3.1f1"), "not a validated engine version"),
            "TMP API": (dict(tmp_api=False), "does not expose the APIs"),
        }
        for label, (options, needle) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as temp:
                result = adapter.inspect_runtime_support(self._game(Path(temp), **options))
                self.assertFalse(result["supported"])
                self.assertTrue(any(needle in reason for reason in result["reasons"]), result["reasons"])

    def test_missing_assembly_registration_schema_and_existing_adapter_are_refused(self):
        def run(mutate, needle):
            with tempfile.TemporaryDirectory() as temp:
                game = self._game(Path(temp))
                mutate(game / "TEST_Data")
                result = adapter.inspect_runtime_support(game)
                self.assertFalse(result["supported"])
                self.assertTrue(any(needle in reason for reason in result["reasons"]), result["reasons"])
        run(lambda d: (d / "Managed/Unity.TextMeshPro.dll").unlink(), "required assembly missing")
        run(lambda d: (d / "RuntimeInitializeOnLoads.json").write_text('{"root":[{"x":1}]}'), "unrecognised schema")
        run(lambda d: (d / "ScriptingAssemblies.json").write_text('{"names":["a"],"types":[]}'), "unrecognised schema")
        run(lambda d: (d / "ScriptingAssemblies.json").write_text('{"names":["UnityEngine.dll"],"types":[0]}'), "Assembly-CSharp")
        run(lambda d: (d / "vntext_tmp_font.cfg").write_text("x"), "already present")
        run(lambda d: (d / "ScriptingAssemblies.json").write_text(json.dumps({"names": ASSEMBLIES["names"] + ["VNTextTmpFonts.dll"], "types": [0, 16, 16]})), "already registered")

    def test_stage_payload_is_exact_deterministic_and_bound_to_the_game(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base)
            before = self._snapshot(game)
            out = base / "out"
            evidence = adapter.stage_adapter_payload(game, out, FONT, TEXT, self._dll(base))
            self.assertEqual(self._snapshot(game), before)
            payload = out / "COPY_TO_GAME_ROOT/TEST_Data"
            digest = hashlib.sha256(FONT.read_bytes()).hexdigest()
            self.assertEqual(sorted(p.relative_to(out / "COPY_TO_GAME_ROOT").as_posix() for p in payload.rglob("*") if p.is_file()), sorted([
                "TEST_Data/Managed/VNTextTmpFonts.dll", "TEST_Data/RuntimeInitializeOnLoads.json", "TEST_Data/ScriptingAssemblies.json", "TEST_Data/vntext_tmp_font.cfg",
                f"TEST_Data/vntext_tmp_font_{digest[:16]}.ttf", f"TEST_Data/vntext_tmp_font_{digest[:16]}.license.txt"]))
            self.assertEqual((payload / f"vntext_tmp_font_{digest[:16]}.license.txt").read_bytes(), (REPO / "vntext/fonts/DejaVuSans.txt").read_bytes())
            startup = json.loads((payload / "RuntimeInitializeOnLoads.json").read_bytes())
            self.assertEqual(startup["root"][:-1], STARTUP["root"])
            self.assertEqual(startup["root"][-1], {"assemblyName": "VNTextTmpFonts", "nameSpace": "VNTextTmpFonts", "className": "Startup", "methodName": "Initialize",
                                                   "loadTypes": 1, "isUnityClass": False})
            assemblies = json.loads((payload / "ScriptingAssemblies.json").read_bytes())
            self.assertEqual((assemblies["names"][-1], assemblies["types"][-1]), ("VNTextTmpFonts.dll", 16))
            config = (payload / "vntext_tmp_font.cfg").read_text(encoding="utf-8").split("\n")
            self.assertEqual(config[:2], [f"vntext_tmp_font_{digest[:16]}.ttf", digest])
            self.assertTrue(set("ĐặngNguyễn") <= set(config[2]))
            self.assertEqual((evidence["glyph_status"], evidence["runtime_status"]), ("PASS", "NOT_PROVEN"))
            self.assertEqual(adapter.verify_staged_payload(game, out)["adapter_sha256"], evidence["adapter_sha256"])
            manifest = write_patch_manifest(out, game, "0.1.24")
            self.assertEqual(sorted(c["path"] for c in manifest["game_checks"]), sorted(f"TEST_Data/Managed/{n}" for n in adapter.REQUIRED_MANAGED))
            files = {f["path"]: f for f in manifest["files"]}
            startup_file = files["TEST_Data/RuntimeInitializeOnLoads.json"]
            self.assertTrue(startup_file["original_exists"])
            self.assertEqual(startup_file["original_sha256"], hashlib.sha256(before["TEST_Data/RuntimeInitializeOnLoads.json"]).hexdigest())
            self.assertFalse(files["TEST_Data/Managed/VNTextTmpFonts.dll"]["original_exists"])

    def test_stage_refuses_glyph_gaps_wrong_font_unsafe_binary_and_unsupported_games(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base)
            dll = self._dll(base)
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "lacks translated glyphs"):
                adapter.stage_adapter_payload(game, base / "o1", FONT, ["日本語"], dll)
            otf = base / "font.otf"
            otf.write_bytes(FONT.read_bytes())
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "TrueType"):
                adapter.stage_adapter_payload(game, base / "o2", otf, TEXT, dll)
            for label, data in {"network": adapter_binary(b"\0UnityWebRequest\0System.Net"), "extra unity module": adapter_binary(b"\0UnityEngine.IOModule"),
                                "not managed": b"MZ only", "missing names": b"MZ" + b"BSJB"}.items():
                with self.subTest(label), self.assertRaises(adapter.UnityTmpAdapterError):
                    adapter.stage_adapter_payload(game, base / ("o3" + label[:3]), FONT, TEXT, self._dll(base, data))
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "IL2CPP"):
                adapter.stage_adapter_payload(self._game(base / "x", il2cpp=True) if (base / "x").mkdir() is None else None, base / "o4", FONT, TEXT, dll)
            with self.assertRaises(adapter.UnityTmpAdapterError):
                adapter.stage_adapter_payload(game, game / "inside", FONT, TEXT, dll)
            self.assertFalse((base / "o1").exists() or (base / "o2").exists())

    def test_verify_detects_tampered_stray_and_drifted_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base)
            out = base / "out"
            adapter.stage_adapter_payload(game, out, FONT, TEXT, self._dll(base))
            data = out / "COPY_TO_GAME_ROOT/TEST_Data"
            adapter.verify_staged_payload(game, out)
            registration = data / "RuntimeInitializeOnLoads.json"
            good = registration.read_bytes()
            registration.write_bytes(good.replace(b"VNTextTmpFonts", b"Evil"))
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "bytes changed"):
                adapter.verify_staged_payload(game, out)
            registration.write_bytes(good)
            (data / "vntext_tmp_font_deadbeefdeadbeef.ttf").write_bytes(b"x")
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "differs from its evidence"):
                adapter.verify_staged_payload(game, out)
            (data / "vntext_tmp_font_deadbeefdeadbeef.ttf").unlink()
            adapter.verify_staged_payload(game, out)
            # game drift: a changed TMP assembly, or changed registration source, invalidates the evidence
            (game / "TEST_Data/Managed/Unity.TextMeshPro.dll").write_bytes(b"MZ other " + b" ".join(adapter.TMP_API_NAMES))
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "no longer matches"):
                adapter.verify_staged_payload(game, out)
            with self.assertRaises(adapter.UnityTmpAdapterError):
                write_patch_manifest(out, game, "0.1.24")

    def test_second_stage_over_an_installed_adapter_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base)
            out = base / "out"
            adapter.stage_adapter_payload(game, out, FONT, TEXT, self._dll(base))
            for relative in (p.relative_to(out / "COPY_TO_GAME_ROOT") for p in (out / "COPY_TO_GAME_ROOT").rglob("*") if p.is_file()):       # simulate an installed game
                target = game / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((out / "COPY_TO_GAME_ROOT" / relative).read_bytes())
            self.assertFalse(adapter.inspect_runtime_support(game)["supported"])
            with self.assertRaisesRegex(adapter.UnityTmpAdapterError, "already"):
                adapter.stage_adapter_payload(game, base / "again", FONT, TEXT, self._dll(base))

    def _pipeline(self, base: Path, game: Path, *, font=FONT, translations=None):
        import os
        from unittest import mock
        from vntext import patch_pipeline
        manifest = base / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        csv = base / "translation.csv"
        csv.write_text("", encoding="utf-8")
        out = base / "out"
        calls = []

        def fake_text_patch(*args, **kwargs):
            calls.append(args)
            (out / "COPY_TO_GAME_ROOT/TEST_Data").mkdir(parents=True, exist_ok=True)
            (out / "COPY_TO_GAME_ROOT/TEST_Data/text.bytes").write_bytes(b"patched text")

        rows = {"k": {"translation": value} for value in (translations or TEXT)}
        with mock.patch.object(patch_pipeline, "detect_patch_engine", return_value="unity"),              mock.patch("vntext.patch_gate.validate_patch_package_identity"), mock.patch("vntext.patch_safety.validate_patch_output"),              mock.patch.object(patch_pipeline, "read_translation_rows", return_value={str(i): {"translation": v} for i, v in enumerate(translations or TEXT)}),              mock.patch.object(patch_pipeline, "_apply_unity_translation_package", side_effect=fake_text_patch),              mock.patch.dict(os.environ, {"VNTEXT_UNITY_TMP_ADAPTER_DLL": str(self._dll(base))}):
            try:
                patch_pipeline.apply_translation_package(str(csv), str(manifest), str(game), str(out), None, replacement_font=str(font))
            finally:
                self.calls = calls
        return out

    def test_pipeline_stages_the_adapter_next_to_the_text_patch_and_binds_the_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base)
            out = self._pipeline(base, game)
            self.assertEqual(len(self.calls), 1)
            self.assertTrue((out / "COPY_TO_GAME_ROOT/TEST_Data/text.bytes").is_file())
            report = json.loads((out / "font_preflight.json").read_text(encoding="utf-8"))
            self.assertEqual((report["glyph_status"], report["mapping_status"], report["runtime_status"], report["compatible"]),
                             ("PASS", "TMP_GLOBAL_FALLBACK_ADAPTER", "NOT_PROVEN", False))
            manifest = write_patch_manifest(out, game, "0.1.24")
            self.assertEqual(manifest["unity_tmp_adapter"]["runtime_status"], "NOT_PROVEN")
            self.assertIn("TEST_Data/text.bytes", {f["path"] for f in manifest["files"]})

    def test_pipeline_refuses_before_any_output_when_a_guard_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game = self._game(base, il2cpp=True)
            with self.assertRaisesRegex(ValueError, "IL2CPP"):
                self._pipeline(base, game)
            self.assertEqual(self.calls, [])
            self.assertFalse((base / "out").exists())
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with self.assertRaisesRegex(ValueError, "lacks translated glyphs"):
                self._pipeline(base, self._game(base), translations=["日本語"])
            self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
