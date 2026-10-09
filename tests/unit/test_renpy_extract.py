from __future__ import annotations

import tempfile
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.renpy_extract import extract_loose_source
from vntext.renpy_toolchain import (SDK_SHA256, RenPyToolchainError, RenPySdk,
    copy_template_workspace, generate_empty_vietnamese_template, install_managed_sdk,
    validate_sdk, managed_sdk_root)


class RenPyExtractTests(unittest.TestCase):
    def test_dev_optional_sdk_cache_uses_shared_environment_only(self):
        repo=Path(__file__).resolve().parents[2]
        with patch.dict(os.environ,{"VNTEXT_DATA_ROOT":str(repo/"DEV_RUN/bootstrap-build/data")}):
            self.assertEqual(managed_sdk_root(),repo/".dev-env/tools/renpy-8.5.3")

    def test_install_boundary_allows_only_dedicated_dev_cache_before_staging(self):
        repo=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"synthetic.zip";archive.write_bytes(b"synthetic guard probe")
            with patch("vntext.renpy_toolchain._sha256",return_value=SDK_SHA256), \
                 patch.object(Path,"mkdir",side_effect=RuntimeError("staging reached")):
                with patch.dict(os.environ,{"VNTEXT_DATA_ROOT":str(repo/"DEV_RUN/bootstrap-build/data")}):
                    with self.assertRaisesRegex(RuntimeError,"staging reached"):
                        install_managed_sdk(archive)
                with patch.dict(os.environ,{"VNTEXT_DATA_ROOT":str(repo/"unowned-sdk-test")}):
                    with self.assertRaisesRegex(RenPyToolchainError,"inside the repository"):
                        install_managed_sdk(archive)

    def test_workspace_rejects_nested_output_and_insufficient_space_before_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"source"; source.mkdir(); (source/"script.rpy").write_text("synthetic")
            with self.assertRaisesRegex(RenPyToolchainError,"ngoài game"):
                copy_template_workspace(source,source/"output")
            target=Path(temp)/"target"
            with patch("vntext.renpy_toolchain.shutil.disk_usage") as usage:
                usage.return_value.free=0
                with self.assertRaisesRegex(RenPyToolchainError,"dung lượng"):
                    copy_template_workspace(source,target)
            self.assertFalse(target.exists())

    def test_dev_workspace_quota_is_checked_before_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp); (source/"script.rpy").write_text("synthetic")
            repo=Path(__file__).resolve().parents[2]
            target=repo/"DEV_RUN/quota-blocked-synthetic-workspace"
            with patch("tests.tools.cleanup_work_artifacts._project_size_snapshot",return_value={
                "complete":True,"within_limit":True,"non_exempt_bytes":99,"limit_bytes":100}), \
                 patch("vntext.renpy_toolchain.shutil.copytree") as copy:
                with self.assertRaisesRegex(RenPyToolchainError,"copy budget"):
                    copy_template_workspace(source,target)
            copy.assert_not_called();self.assertFalse(target.exists())

    def test_template_cancel_stops_ready_synthetic_child(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"game").mkdir(); ready=root/"ready"
            cli=root/"synthetic_cli.py"
            cli.write_text("import sys,time\nfrom pathlib import Path\nPath(sys.argv[1], 'ready').write_text('ready')\ntime.sleep(20)\n")
            sdk=RenPySdk(root,Path(sys.executable),cli,"synthetic-only")
            import subprocess
            real_popen=subprocess.Popen; children=[]
            def spawn(*args,**kwargs):
                proc=real_popen(*args,**kwargs); children.append(proc); return proc
            with patch("vntext.renpy_toolchain.subprocess.Popen",side_effect=spawn):
                with self.assertRaisesRegex(RenPyToolchainError,"cancelled"):
                    generate_empty_vietnamese_template(sdk,root,timeout=3,is_cancelled=ready.exists)
            self.assertTrue(ready.exists())
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())

    def test_dialogue_identity_comes_only_from_template_and_duplicates_remain_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); game = root / "game"; game.mkdir()
            (game / "script.rpy").write_text('label start:\n    "Come here."\n    e "Come here."\n    menu:\n        "Open the door":\n            pass\n    $ status = _("Ready: %(count)d")\n', encoding="utf-8")
            template = game / "tl" / "vietnamese"; template.mkdir(parents=True)
            (template / "script.rpy").write_text('translate vietnamese start_a:\n    # "Come here."\n    ""\ntranslate vietnamese start_b:\n    # e "Come here."\n    e ""\n', encoding="utf-8")
            main, review, _stats = extract_loose_source(root, template_root=template)
            dialogue = [row for row in main if row.import_method == "renpy_dialogue"]
            self.assertEqual([row.locator["native_id"] for row in dialogue], ["start_a", "start_b"])
            self.assertNotEqual(dialogue[0].key, dialogue[1].key)
            self.assertEqual([row.source_text for row in main if row.import_method == "renpy_string"], ["Open the door", "Ready: %(count)d"])
            self.assertEqual(review, [])

    def test_missing_template_never_guesses_dialogue_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); game = root / "game"; game.mkdir()
            (game / "script.rpy").write_text('label start:\n    "Hello"\n', encoding="utf-8")
            main, review, _stats = extract_loose_source(root)
            self.assertEqual(main, [])
            self.assertEqual(len(review), 1)
            self.assertEqual(review[0].locator["native_id"], "")

    def test_sdk_validation_is_pinned_and_rejects_wrong_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "lib" / "py3-windows-x86_64").mkdir(parents=True)
            (root / "renpy.py").write_text("# placeholder", encoding="utf-8")
            (root / "lib" / "py3-windows-x86_64" / "python.exe").write_bytes(b"")
            with patch("vntext.renpy_toolchain.subprocess.run") as run:
                run.return_value.returncode = 0; run.return_value.stdout = "Ren'Py 8.5.3"; run.return_value.stderr = ""
                self.assertEqual(validate_sdk(root).version, "8.5.3")
                run.return_value.stdout = "Ren'Py 8.6.0"
                with self.assertRaises(RenPyToolchainError):
                    validate_sdk(root)

    def test_managed_install_rejects_unverified_archive_before_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "sdk.zip"; archive.write_bytes(b"not an sdk")
            with self.assertRaises(RenPyToolchainError):
                install_managed_sdk(archive)
