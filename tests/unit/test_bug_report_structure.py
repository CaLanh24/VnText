"""A report from a game nobody here owns must let us rebuild the failing structure exactly, without a single original name or string."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.lib.work_paths import work_temp_dir
from tests.tools.synth_from_report import synthesize_native_blocks
from vntext.app_tasks import run_extract_task
from vntext.bug_report import SCHEMA, build_report
from vntext.renpy_extract import parse_renpy_translation_templates
from vntext.shape_mask import mask_block, rebuild_text

WORK = work_temp_dir("bug-report-structure")
NL = chr(10)
SECRETS = ("TopSecretHero", "ZorbaTheGreat", "Mystery Dialogue Line", "hidden_tag_fn", "Quillfeather", "secret_game.rpy")
TEMPLATE = (
    "# game/script.rpy:2" + NL + "translate vietnamese native_only:" + NL + NL + '    # "Native only"' + NL + '    ""' + NL + NL +
    "# game/secret_game.rpy:3" + NL + "translate vietnamese python:" + NL + NL +
    '    config.custom_text_tags["ZorbaTheGreat"] = hidden_tag_fn("Mystery Dialogue Line {b}x{/b} [TopSecretHero]")' + NL + NL +
    "# game/secret_game.rpy:9" + NL + "translate vietnamese style Quillfeather:" + NL + NL + "    size 20" + NL + NL +
    "# game/secret_game.rpy:12" + NL + "translate vietnamese multi_say:" + NL + NL + '    # TopSecretHero "Mystery Dialogue Line"' + NL +
    '    # TopSecretHero "Another"' + NL + '    TopSecretHero ""' + NL + '    TopSecretHero ""' + NL
)


class BugReportStructureTests(unittest.TestCase):
    def _extract(self, base: Path):
        root = base / "game copy"
        (root / "game").mkdir(parents=True)
        (root / "game" / "script.rpy").write_text("label start:" + NL + '    "Native only"' + NL, encoding="utf-8")
        (root / "game" / "secret_game.rpy").write_text("init python:" + NL + "    pass" + NL, encoding="utf-8")
        out = base / "out"
        completed = []

        def generate(_sdk, workspace, **_kwargs):
            template = workspace / "game" / "tl" / "vietnamese"
            template.mkdir(parents=True)
            (template / "script.rpy").write_text(TEMPLATE, encoding="utf-8")

        roomy = {"complete": True, "within_limit": True, "non_exempt_bytes": 0, "limit_bytes": 1 << 40}
        with (
            patch("vntext.app_tasks._run_unity_preflight"),
            patch("vntext.renpy_toolchain.validate_sdk", return_value=SimpleNamespace(version="8.5.3")),
            patch("vntext.renpy_toolchain.generate_empty_vietnamese_template", side_effect=generate),
            patch("tests.tools.cleanup_work_artifacts._project_size_snapshot", return_value=roomy),
        ):
            run_extract_task(str(root), str(out), "safe", "balanced", True, renpy_sdk_path="C:/sdk", renpy_sdk_action="existing",
                             progress=lambda _x: None, log=lambda _x: None, complete=completed.append)
        return root, out, completed[-1]

    def test_report_of_unsupported_blocks_replays_the_same_failure_and_leaks_nothing(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root, out, result = self._extract(Path(temp))
            self.assertNotEqual("FAILED", result["extract_status"], result)
            target = build_report(root, out, extract_status=out / "extract_status.json")
            with zipfile.ZipFile(target) as archive:
                blob = "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())
                report = json.loads(archive.read("report.json"))
            self.assertEqual(SCHEMA, report["schema"])
            self.assertEqual(2, report["schema"])
            for secret in SECRETS + (temp,):
                self.assertNotIn(secret.casefold(), blob.casefold(), secret)
            blocks = report["structure"]["renpy_native_blocks"]
            self.assertEqual(3, len(blocks))
            self.assertEqual({"python", "style", "identifier"}, {b["target_class"] for b in blocks})
            counters = report["structure"]["counters"]
            self.assertEqual(3, counters["native_unresolved_blocks"])
            # Rebuild the blocks from the masked shapes alone and run them through the same parser: same verdicts, same order.
            rebuilt = synthesize_native_blocks(report)
            original_unresolved, replay_unresolved = [], []
            with tempfile.TemporaryDirectory(dir=WORK) as t2:
                for name, text, ledger in (("orig", TEMPLATE, original_unresolved), ("replay", rebuilt, replay_unresolved)):
                    directory = Path(t2) / name / "game" / "tl" / "vietnamese"
                    directory.mkdir(parents=True)
                    (directory / "script.rpy").write_text(text, encoding="utf-8")
                    parse_renpy_translation_templates(Path(t2) / name / "game" / "tl", language="vietnamese" if name == "orig" else None, unresolved=ledger)
            self.assertEqual(3, len(original_unresolved))
            self.assertEqual(len(original_unresolved), len(replay_unresolved))
            for before, after in zip(original_unresolved, replay_unresolved):
                self.assertEqual(before["native_id"].split(" ")[0] in {"python", "style"}, after["native_id"].split(" ")[0] in {"python", "style"})
                self.assertEqual(before["reason"].split(":", 2)[-1].strip()[:40], after["reason"].split(":", 2)[-1].strip()[:40])

    def test_mask_keeps_syntax_and_replaces_every_name_and_string(self):
        text = 'define hidden_tag_fn = Quillfeather("Mystery Dialogue Line", 42)' + NL + '    # ZorbaTheGreat "Secret"' + NL
        shape = mask_block(text)
        blob = json.dumps(shape)
        for secret in ("hidden_tag_fn", "Quillfeather", "Mystery", "ZorbaTheGreat", "Secret"):
            self.assertNotIn(secret, blob)
        self.assertEqual("define", shape[0]["tokens"][0])
        self.assertTrue(shape[1]["comment"])
        rebuilt = rebuild_text(shape)
        self.assertEqual(2, len(rebuilt.strip().splitlines()))
        self.assertTrue(rebuilt.startswith("define "))
        self.assertEqual(len(text.splitlines()[0]), len(rebuilt.splitlines()[0]))

    def test_schema_one_reports_still_load_and_synthesize(self):
        from tests.tools.synth_from_report import synthesize
        report = {"schema": 1, "files": [{"path": "game/script.rpy", "size": 10, "header": ""}]}
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            self.assertTrue((synthesize(report, Path(temp) / "x") / "game" / "script.rpy").is_file())
        self.assertEqual("", synthesize_native_blocks(report))


if __name__ == "__main__":
    unittest.main()
