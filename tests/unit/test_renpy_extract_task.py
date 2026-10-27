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
            error=completed[-1]["error"]
            # Actionable copy: names the SDK, the required version, the next action and the cause.
            self.assertIn("SDK Ren'Py",error)
            self.assertIn("8.5.3",error)
            self.assertIn("chọn lại SDK",error)
            self.assertIn("wrong version",error)

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

    FIXTURE_OPTIONS = 'define config.name = _("Synthetic Village")\n'
    FIXTURE_SCRIPT = (
        'define e = Character("Eileen")\n'
        'label start:\n'
        '    e "Welcome to the village, traveler."\n'
        '    e "The gate is open, but the road is long."\n'
        '    menu:\n'
        '        "Take the north road":\n'
        '            e "A cold wind blows from the mountains."\n'
        '        "Rest at the inn":\n'
        '            e "The innkeeper smiles and offers you a warm meal."\n'
        '    e "Come back soon."\n'
        '    return\n'
    )

    def _no_sdk_run(self, temp, action="none", sdk_path="", extra_patch=None, options_text=None, script_text=None):
        root = Path(temp) / "game"
        (root / "game").mkdir(parents=True)
        (root / "game" / "options.rpy").write_text(self.FIXTURE_OPTIONS if options_text is None else options_text, encoding="utf-8")
        (root / "game" / "script.rpy").write_text(self.FIXTURE_SCRIPT if script_text is None else script_text, encoding="utf-8")
        out = Path(temp) / "out"
        completed, logs = [], []
        with patch("vntext.app_tasks._run_unity_preflight"), patch("vntext.renpy_toolchain.managed_sdk", return_value=None), \
                patch.dict("os.environ", {}, clear=True):
            if extra_patch is not None:
                with extra_patch:
                    run_extract_task(str(root), str(out), "safe", "balanced", True, renpy_sdk_path=sdk_path, renpy_sdk_action=action,
                                     progress=lambda _x: None, log=logs.append, complete=completed.append)
            else:
                run_extract_task(str(root), str(out), "safe", "balanced", True, renpy_sdk_path=sdk_path, renpy_sdk_action=action,
                                 progress=lambda _x: None, log=logs.append, complete=completed.append)
        return root, out, completed, logs

    def test_no_sdk_loose_source_exports_review_only_with_empty_main_and_cannot_translate_or_patch(self):
        """Owner decision 2026-10-27: static scan only for a review list; MAIN empty, never translated/patched, always PARTIAL."""
        import csv as csv_module
        from vntext.patch_gate import validate_patch_package_identity
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root, out, completed, logs = self._no_sdk_run(temp)
            self.assertEqual(len(completed), 1, completed)
            done = completed[0]
            # 3 strings (title + two menu choices) and 5 dialogue lines: all review-only, nothing in MAIN, no symmetry exception
            self.assertEqual(done["review_only"], 8, done)
            self.assertFalse(done["ok"])
            self.assertFalse(done["complete"])
            self.assertTrue(done["renpy_sdk_missing"])
            self.assertEqual(done["extract_status"], "PARTIAL")
            self.assertNotIn("symmetry", done["error"])
            self.assertIn("Đã xuất 8 dòng chỉ để xem lại", done["error"])
            status = json.loads((out / "extract_status.json").read_text(encoding="utf-8"))
            self.assertFalse(status["complete"])
            self.assertEqual((status["status"], status["main"], status["review"]), ("PARTIAL", 0, 8))
            # the package exists, but translation.csv has no data row to translate
            with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv_module.DictReader(stream)), [])
            review_text = (out / "review_only.csv").read_text(encoding="utf-8-sig")
            for expected in ("Synthetic Village", "Take the north road", "Rest at the inn", "Welcome to the village, traveler.", "Come back soon."):
                self.assertIn(expected, review_text)
            with (out / "review_only.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(len(list(csv_module.DictReader(stream))), 8)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(len(manifest["entries"]), 8)
            for entry in manifest["entries"]:   # evidence rows only: flagged review, no proof, no native contract/identity
                self.assertTrue(entry["review_only"])
                self.assertFalse(entry.get("patch_proof"))
                self.assertNotIn("native_contract", entry)
                self.assertFalse(entry["locator"].get("native_id"))
            # final Patch is refused by the extract status (and there is nothing to patch)
            with self.assertRaisesRegex(ValueError, "Extraction is incomplete; final Patch is blocked"):
                validate_patch_package_identity(out / "translation.csv", manifest)
            self.assertTrue(any("không có dòng nào được dịch hay patch" in line for line in logs))
            self.assertEqual((root / "game" / "script.rpy").read_text(encoding="utf-8"), self.FIXTURE_SCRIPT)

    def test_no_sdk_static_export_with_zero_rows_is_still_partial_never_empty_or_complete(self):
        """Owner decision 2026-10-27: no-SDK extract_status is always PARTIAL, also when the static scan found nothing to review."""
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            _root, out, completed, _logs = self._no_sdk_run(temp, options_text="define config.version = \"1\"\n", script_text="label start:\n    return\n")
            self.assertEqual(len(completed), 1, completed)
            done = completed[0]
            self.assertEqual(done["extract_status"], "PARTIAL", done)
            self.assertFalse(done["complete"])
            self.assertFalse(done["ok"])
            self.assertTrue(done["renpy_sdk_missing"])
            self.assertEqual(done["review_only"], 0)
            status = json.loads((out / "extract_status.json").read_text(encoding="utf-8"))
            self.assertEqual((status["status"], status["complete"], status["main"], status["review"]), ("PARTIAL", False, 0, 0))

    def test_loose_scan_review_only_never_invents_native_identity_or_proof(self):
        from vntext.renpy_extract import extract_loose_source
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            game = Path(temp) / "game"
            (game / "game").mkdir(parents=True)
            (game / "game" / "options.rpy").write_text(self.FIXTURE_OPTIONS, encoding="utf-8")
            (game / "game" / "script.rpy").write_text(self.FIXTURE_SCRIPT, encoding="utf-8")
            main, review, stats = extract_loose_source(game, review_only=True)
            self.assertEqual(main, [])
            self.assertEqual(len(review), 8)
            self.assertTrue(stats["review_only"])
            for entry in review:
                self.assertEqual(entry.patch_proof, {})
                self.assertTrue(entry.review_only)
                self.assertEqual(entry.native_contract, {})
                self.assertFalse(entry.locator.get("native_id"))
                self.assertNotIn("unit_type", entry.locator)
            # a template could supply native identities: the combination is rejected, not silently honoured
            with self.assertRaises(ValueError):
                extract_loose_source(game, template_root=game, review_only=True)
            # the default (template-backed) mode is unchanged: menu/strings stay MAIN candidates there
            main_default, _review_default, stats_default = extract_loose_source(game)
            self.assertEqual(len(main_default), 3)
            self.assertFalse(stats_default["review_only"])

    def test_sdk_download_failure_reports_the_cause_and_no_review_count(self):
        from vntext.renpy_toolchain import RenPyToolchainError
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            failing = patch("vntext.renpy_toolchain.download_and_install_managed_sdk", side_effect=RenPyToolchainError("offline: connection refused"))
            _root, out, completed, _logs = self._no_sdk_run(temp, action="download", extra_patch=failing)
            done = completed[0]
            self.assertFalse(done["ok"])
            self.assertTrue(done["renpy_sdk_missing"])
            self.assertIn("Tải SDK Ren'Py 8.5.3 chưa hoàn tất", done["error"])
            self.assertIn("offline: connection refused", done["error"])
            self.assertEqual(done["review_only"], 0, "no evidence exists: the generic sentinel must not read as one review row")
            self.assertEqual(done["blocked"], 0)
            self.assertNotIn("extract_status", done)
            self.assertFalse((out / "translation.csv").exists())
            self.assertEqual([item.name for item in out.glob("renpy-sdk-*")], [], "no archive/partial is left behind")

    def test_chosen_sdk_that_is_not_valid_reports_the_cause_and_no_review_count(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            _root, out, completed, _logs = self._no_sdk_run(temp, action="existing", sdk_path=str(Path(temp) / "not-an-sdk"))
            done = completed[0]
            self.assertFalse(done["ok"])
            self.assertTrue(done["renpy_sdk_missing"])
            self.assertIn("SDK Ren'Py đã chọn chưa hợp lệ", done["error"])
            self.assertEqual((done["review_only"], done["blocked"]), (0, 0))
            self.assertFalse((out / "translation.csv").exists())

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
