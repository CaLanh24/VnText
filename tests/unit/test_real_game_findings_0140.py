"""Findings from running real games (0.1.40): each fix has a check that does not need a game."""
import builtins
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


class RealGameFindings0140(unittest.TestCase):
    def test_canonical_value_is_unchanged_by_the_faster_type_checks(self):
        from vntext.traceability import _canonical_value
        value = {"b": [1, (2, None, True)], "a": OrderedDict(x=1.5), 3: "s"}
        self.assertEqual({"3": "s", "a": {"x": 1.5}, "b": [1, [2, None, True]]}, _canonical_value(value))
        self.assertEqual("<class 'object'>", _canonical_value(object))

    def test_missing_unity_reader_is_an_error_not_a_silent_empty_result(self):
        from vntext.extract_unity import extract_unity_typetree
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "UnityPy":
                raise ImportError("blocked for the test")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.__import__", side_effect=blocked):
            with self.assertRaisesRegex(RuntimeError, "UnityPy"):
                list(extract_unity_typetree(Path(tmp) / "x.assets", Path(tmp)))

    def test_label_index_matches_the_old_backwards_scan(self):
        from vntext import renpy_extract as r
        lines = ["label a:", "    x", "", "label b:", "    y", "#c", "label c: # t", "    z"]

        def old(lines, n):
            for raw in reversed(lines[: max(0, n - 1)]):
                if raw[:1].isspace():
                    continue
                m = r._LABEL.fullmatch(raw.strip())
                if m:
                    return f"label:{m.group('name')}"
            return ""

        for n in range(0, len(lines) + 3):
            self.assertEqual(old(lines, n), r._source_context_group(lines, n), n)

    def test_csv_elsewhere_note_and_friendly_image_names_exist_in_the_app(self):
        vm = (ROOT / "wpf_app/VNText.Studio.App/ViewModels/MainViewModel.cs").read_text(encoding="utf-8")
        xaml = (ROOT / "wpf_app/VNText.Studio.App/MainWindow.xaml").read_text(encoding="utf-8")
        probe = (ROOT / "wpf_app/VNText.Studio.App/Services/ImagePackageProbe.cs").read_text(encoding="utf-8")
        self.assertIn("CsvElsewhereNote", vm)
        self.assertEqual(2, xaml.count("CsvElsewhereNote, Converter"))                 # translate page and patch page
        self.assertIn("FriendlyName(S(\"source\"))", probe)

    def test_publisher_keeps_the_preflight_output(self):
        text = (ROOT / "release/publish.ps1").read_text(encoding="utf-8")
        self.assertIn("-release_verify.log", text)
        self.assertIn("DEV release_verify FAILED", text)

    def test_setup_payload_tool_is_in_the_repository(self):
        self.assertTrue((ROOT / "release/ResourceDump.cs").is_file())
        self.assertIn("Payload.zip", (ROOT / "release/ResourceDump.cs").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "release/extract_setup_payload.py").is_file())


if __name__ == "__main__":
    unittest.main()
