from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.lib.work_paths import work_temp_dir

from vntext.app_tasks import run_extract_task
from vntext_worker.task_runners import run_extract_worker

WORK = work_temp_dir("renpy-extract-task")


class RenPyExtractTaskTests(unittest.TestCase):
    def test_rpa_source_without_sdk_reports_recovery_without_loose_parser_fallback(self):
        from tests.unit.test_renpy_archive import write_rpa
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp) / "game"
            (root / "game").mkdir(parents=True)
            write_rpa(root / "game/scripts.rpa", {"game/script.rpy": b'label start:\n    e "Archive line"\n'})
            completed = []
            with patch("vntext.renpy_toolchain.managed_sdk", return_value=None), \
                 patch("vntext.renpy_extract.extract_loose_source") as fallback:
                run_extract_task(str(root), str(Path(temp) / "out"), "safe", "balanced", True,
                                 renpy_sdk_action="none", progress=lambda _: None, log=lambda _: None,
                                 complete=completed.append)
            fallback.assert_not_called()
            self.assertEqual(len(completed), 1)
            self.assertFalse(completed[0]["ok"])
            self.assertFalse(completed[0]["complete"])
            self.assertTrue(completed[0]["renpy_sdk_missing"])
            self.assertIn("cần SDK 8.5.3", completed[0]["error"])

    def test_rpa_source_uses_native_sdk_route_and_records_archive_identity(self):
        from tests.unit.test_renpy_archive import write_rpa
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root=Path(temp)/"game";(root/"game").mkdir(parents=True)
            write_rpa(root/"game/scripts.rpa",{"game/script.rpy":b'label start:\n    e "Archive line"\n'})
            sdk=SimpleNamespace(version="8.5.3")
            def generate(_sdk,workspace,**_kwargs):
                templates=Path(workspace)/"game/tl/vietnamese";templates.mkdir(parents=True)
                (templates/"script.rpy").write_text(
                    '# game/script.rpy:2\ntranslate vietnamese archive_line:\n\n'
                    '    # e "Archive line"\n    e ""\n',encoding="utf-8")
                return SimpleNamespace(returncode=0,stdout="",stderr="")
            completed=[]
            with patch("vntext.app_tasks._run_unity_preflight",return_value={}), \
                 patch("vntext.renpy_toolchain.managed_sdk",return_value=sdk), \
                 patch("vntext.renpy_toolchain.generate_empty_vietnamese_template",side_effect=generate):
                run_extract_task(str(root),str(Path(temp)/"out"),"safe","balanced",True,
                                 progress=lambda _:None,log=lambda _:None,complete=completed.append)
            self.assertTrue(completed)
            self.assertFalse(completed[0].get("ok"),completed[0])
            self.assertEqual(completed[0]["extract_status"],"PARTIAL")
            document=json.loads((Path(temp)/"out/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(document["entries"]),1)
            provenance=document["entries"][0]["native_contract"]["provenance"]["source_container"]
            self.assertEqual(provenance["member_name"],"game/script.rpy")
            self.assertFalse(provenance["runtime_execution_proven"])

    def test_unsupported_engine_never_falls_into_generic_extractor(self):
        for kind in ("compiled", "mixed", "unknown", "missing"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=WORK) as temp:
                root = Path(temp) / "input"
                if kind != "missing":
                    root.mkdir()
                if kind in {"compiled", "mixed"}:
                    (root / "game").mkdir()
                    (root / "game" / ("script.rpyc" if kind == "compiled" else "script.rpy")).write_text("synthetic")
                if kind == "mixed":
                    (root / "Demo_Data").mkdir()
                completed = []
                with patch("vntext.app_tasks.extract_project") as fallback:
                    run_extract_task(str(root), str(Path(temp) / "out"), "safe", "balanced", True,
                                     progress=lambda _: None, log=lambda _: None, complete=completed.append)
                fallback.assert_not_called()
                self.assertFalse(completed[-1]["complete"])
                self.assertFalse(completed[-1]["ok"])
                self.assertTrue(completed[-1]["error"])

    def test_generic_text_keeps_explicit_supported_route_and_empty_is_not_complete(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp) / "input"; root.mkdir()
            text = root / "story.txt"; text.write_text("", encoding="utf-8")
            completed = []
            run_extract_task(str(root), str(Path(temp) / "out"), "safe", "balanced", True,
                             progress=lambda _: None, log=lambda _: None, complete=completed.append)
            self.assertFalse(completed[-1]["complete"])
            self.assertEqual(completed[-1]["extract_status"], "EMPTY")
            self.assertTrue((Path(temp) / "out" / "manifest.json").is_file())

    def test_extract_does_not_overwrite_existing_package(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root=Path(temp)/"input"; root.mkdir(); (root/"story.txt").write_text("Hello there.")
            out=Path(temp)/"out"; out.mkdir(); csv=out/"translation.csv"; csv.write_bytes(b"owner data")
            completed=[]
            run_extract_task(str(root),str(out),"safe","balanced",True,
                             progress=lambda _:None,log=lambda _:None,complete=completed.append)
            self.assertEqual(csv.read_bytes(),b"owner data")
            self.assertFalse(completed[-1]["ok"])

    def test_sdk_failure_and_cancel_dispose_scratch_and_preserve_input(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled), tempfile.TemporaryDirectory(dir=WORK) as temp:
                root=Path(temp)/"input"; (root/"game").mkdir(parents=True)
                script=root/"game/script.rpy"; original=b'label start:\n    "Hello"\n'; script.write_bytes(original)
                out=Path(temp)/"out"; completed=[]; workspaces=[]
                state={"cancelled":False}
                def fail(_sdk, workspace, **kwargs):
                    workspaces.append(workspace)
                    self.assertEqual((workspace/"game/script.rpy").read_bytes(),original)
                    state["cancelled"]=cancelled
                    raise RuntimeError("synthetic native error")
                with patch("vntext.renpy_toolchain.validate_sdk",return_value=SimpleNamespace(version="8.5.3")), \
                     patch("vntext.renpy_toolchain.generate_empty_vietnamese_template",side_effect=fail):
                    run_extract_task(str(root),str(out),"safe","balanced",True,renpy_sdk_path="synthetic",renpy_sdk_action="existing",
                                     progress=lambda _:None,log=lambda _:None,complete=completed.append,is_cancelled=lambda:state["cancelled"])
                self.assertEqual(script.read_bytes(),original)
                self.assertEqual(len(workspaces),1)
                self.assertFalse(workspaces[0].exists())
                self.assertFalse(completed[-1]["complete"])
                self.assertEqual(completed[-1]["error"],"cancelled" if cancelled else "synthetic native error")

    def test_explicit_invalid_sdk_is_actionable_and_does_not_fallback(self):
        from vntext.renpy_toolchain import RenPyToolchainError
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root=Path(temp)/"input"; (root/"game").mkdir(parents=True)
            (root/"game/script.rpy").write_text('label start:\n    "Hello"\n')
            completed=[]
            with patch("vntext.renpy_toolchain.validate_sdk",side_effect=RenPyToolchainError("wrong version")), \
                 patch("vntext.renpy_extract.extract_loose_source") as fallback:
                run_extract_task(str(root),str(Path(temp)/"out"),"safe","balanced",True,
                                 renpy_sdk_action="existing",renpy_sdk_path="synthetic",progress=lambda _:None,
                                 log=lambda _:None,complete=completed.append)
            fallback.assert_not_called()
            self.assertFalse(completed[-1]["ok"])
            self.assertTrue(completed[-1]["renpy_sdk_missing"])
            self.assertIn("cần SDK 8.5.3",completed[-1]["error"])

    def test_result_counts_match_the_filtered_package_in_both_modes(self):
        import json
        from vntext.package_io import read_csv_rows_file
        for separate in (True,False):
            with self.subTest(separate=separate), tempfile.TemporaryDirectory(dir=WORK) as temp:
                root=Path(temp)/"input"; root.mkdir()
                (root/"story.txt").write_text("Hello, how are you?\nAssets/Textures/Player.prefab\n",encoding="utf-8")
                before=(root/"story.txt").read_bytes();out=Path(temp)/"out";completed=[]
                run_extract_task(str(root),str(out),"safe","balanced",separate,
                                 progress=lambda _:None,log=lambda _:None,complete=completed.append)
                stats=json.loads((out/"manifest.json").read_text(encoding="utf-8"))["stats"]
                status=json.loads((out/"extract_status.json").read_text(encoding="utf-8"))
                rows=read_csv_rows_file(out/"translation.csv")[1]
                self.assertGreater(len(rows),0)
                self.assertEqual(stats["translation_csv_entries"],len(rows))
                self.assertEqual(status["main"],stats["main_entries"])
                self.assertEqual(completed[-1]["review_only"],status["review"])
                self.assertIn(str(len(rows))+" dòng translation.csv",completed[-1]["summary"])
                self.assertEqual((root/"story.txt").read_bytes(),before)

    def test_sdk_route_uses_native_units_without_source_parser_promotion(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp) / "gamecopy"; (root / "game").mkdir(parents=True)
            (root / "game" / "script.rpy").write_text(
                'label start:\n    $ code_literal = "Only code"\n    "Native only"\n',
                encoding="utf-8",
            )
            out = Path(temp) / "out"; completed = []; workspaces = []

            def generate(_sdk, workspace, **_kwargs):
                workspaces.append(workspace)
                template = workspace / "game" / "tl" / "vietnamese"
                template.mkdir(parents=True)
                (template / "script.rpy").write_text(
                    "# game/script.rpy:3\n"
                    "translate vietnamese native_only:\n\n"
                    '    # "Native only"\n'
                    '    ""\n',
                    encoding="utf-8",
                )

            with (
                patch("vntext.app_tasks._run_unity_preflight"),
                patch("vntext.renpy_toolchain.validate_sdk", return_value=SimpleNamespace(version="8.5.3")),
                patch("vntext.renpy_toolchain.generate_empty_vietnamese_template", side_effect=generate),
                patch("vntext.renpy_extract.extract_loose_source", side_effect=AssertionError("source parser called")),
            ):
                run_extract_task(
                    str(root),
                    str(out),
                    "safe",
                    "balanced",
                    True,
                    renpy_sdk_path="C:/sdk",
                    renpy_sdk_action="existing",
                    progress=lambda _x: None,
                    log=lambda _x: None,
                    complete=completed.append,
                )

            self.assertTrue(completed[-1]["complete"])
            self.assertEqual(len(workspaces), 1)
            self.assertFalse(workspaces[0].exists())
            self.assertEqual(completed[-1]["review_only"], 0)
            manifest = (out / "manifest.json").read_text(encoding="utf-8")
            self.assertIn('"native_id": "native_only"', manifest)
            self.assertNotIn("Only code", manifest)

    def test_engine_common_exclusions_do_not_block_game_owned_completion(self):
        import json
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp) / "gamecopy"
            (root / "game").mkdir(parents=True)
            (root / "game" / "script.rpy").write_text('label start:\n    "Game line"\n', encoding="utf-8")
            common = root / "renpy" / "common" / "common.rpy"
            common.parent.mkdir(parents=True)
            common.write_text('    $ value = _("Common menu")\n', encoding="utf-8")
            out = Path(temp) / "out"
            completed = []

            def generate(_sdk, workspace, **_kwargs):
                template = workspace / "game" / "tl" / "vietnamese"
                template.mkdir(parents=True)
                (template / "script.rpy").write_text(
                    "# game/script.rpy:2\n"
                    "translate vietnamese game_line:\n\n"
                    '    # "Game line"\n'
                    '    ""\n\n'
                    "translate vietnamese strings:\n\n"
                    "    # renpy/common/common.rpy:1\n"
                    '    old "Common menu"\n'
                    '    new ""\n\n'
                    "    # renpy/common/00translation.rpy:1\n"
                    '    old "SDK-only common"\n'
                    '    new ""\n',
                    encoding="utf-8",
                )

            with (
                patch("vntext.app_tasks._run_unity_preflight"),
                patch("vntext.renpy_toolchain.validate_sdk", return_value=SimpleNamespace(version="8.5.3")),
                patch("vntext.renpy_toolchain.generate_empty_vietnamese_template", side_effect=generate),
            ):
                run_extract_task(
                    str(root), str(out), "safe", "balanced", True,
                    renpy_sdk_path="C:/sdk", renpy_sdk_action="existing",
                    progress=lambda _: None, log=lambda _: None, complete=completed.append,
                )

            status = json.loads((out / "extract_status.json").read_text(encoding="utf-8"))
            exclusions = json.loads((out / "renpy_engine_common_exclusions.json").read_text(encoding="utf-8"))
            self.assertTrue(completed[-1]["complete"])
            self.assertTrue(completed[-1]["native_accounting_complete"])
            self.assertEqual(completed[-1]["native_units"], 3)
            self.assertEqual(completed[-1]["native_accounted"], 3)
            self.assertEqual(status["status"], "COMPLETE")
            self.assertEqual(status["main"], 1)
            self.assertEqual(status["review"], 0)
            self.assertEqual(status["excluded_engine_common"], 2)
            self.assertEqual(exclusions["count"], 2)
            self.assertIn("loại 2 chuỗi Ren'Py common", completed[-1]["summary"])

    def test_no_sdk_extracts_without_guessing_native_ids(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp) / "game"; (root / "game").mkdir(parents=True)
            (root / "game" / "script.rpy").write_text('label start:\n    "Hello"\n', encoding="utf-8")
            out = Path(temp) / "out"; completed = []
            logs = []
            with patch("vntext.app_tasks._run_unity_preflight"), patch("vntext.renpy_toolchain.managed_sdk", return_value=None), patch.dict("os.environ", {}, clear=True):
                run_extract_task(str(root), str(out), "safe", "balanced", True, progress=lambda _x: None, log=logs.append, complete=completed.append)
            self.assertTrue((out / "translation.csv").is_file())
            self.assertEqual(completed[-1]["review_only"], 1)
            self.assertFalse(completed[-1]["complete"])
            self.assertTrue(completed[-1]["renpy_sdk_missing"])
            self.assertIn("thiếu công cụ Ren'Py", completed[-1]["summary"])
            self.assertIn("chưa có công cụ Ren'Py", completed[-1]["error"])
            self.assertTrue(any("Kết quả chưa đầy đủ" in line for line in logs))

    def test_worker_forwards_explicit_sdk_choice(self):
        callbacks = (lambda _x: None, lambda _x: None, lambda _x: None)
        with patch("vntext_worker.task_runners._make_callbacks", return_value=callbacks), patch("vntext_worker.task_runners.run_extract_task") as task:
            run_extract_worker(
                "renpy-sdk",
                {"src": "C:/game", "out": "C:/package", "renpy_sdk_path": "C:/sdk", "renpy_sdk_action": "existing"},
                lambda: False,
            )
        self.assertEqual(task.call_args.kwargs["renpy_sdk_path"], "C:/sdk")
        self.assertEqual(task.call_args.kwargs["renpy_sdk_action"], "existing")
