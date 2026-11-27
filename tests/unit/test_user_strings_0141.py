"""0.1.41: the words a person reads must be plain Vietnamese.  Scans every static string of every screen (all XAML), the Vietnamese string literals of the
app code, the catalog keys, the English catalog values (no Vietnamese left in an English screen) and the worker messages of the image and resource tasks.
Only the strings are scanned - identifiers, task ids and file names stay as they are."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "wpf_app" / "VNText.Studio.App"
VI = re.compile("[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", re.I)
# developer words; file names (translation.csv, review_only.csv, COPY_TO_GAME_ROOT ...) are not words of a sentence
BANNED = re.compile(r"(?<![\w.])(review|Review|REVIEW|region|Region|OCR|pixel|pixels|glyph|render|Render|output|Output|pending|blocked|File|crop|Crop|preview|Preview|clone|Clone|stale|resource|resources)(?![\w.]*\.(?:csv|json|txt))(?![\w])")
ALLOWED_CONTEXT = (
    "Windows OCR", "tessdata", "review_only", "OCR_READY", "Cloud Repair",
)


def _xaml_strings(text):
    out = []
    for m in re.finditer(r'(?<![:\w])(?:Content|Text|Header|ToolTip|Title|Description|Label)="([^"{][^"]*)"|AutomationProperties\.(?:Name|HelpText)="([^"{][^"]*)"', text):
        out.append(m.group(1) or m.group(2))
    return out


def _cs_literals(text):
    return [s for s in re.findall(r'"((?:[^"\\\n]|\\.){6,})"', text)]


def _hits(strings):
    strings = [re.sub(r"{[^}]*}", "", s) for s in strings]
    bad = []
    for s in strings:
        if not VI.search(s) or any(a in s for a in ALLOWED_CONTEXT):
            continue
        m = BANNED.search(s)
        if m:
            bad.append(f"[{m.group(1)}] {s[:140]}")
    return sorted(set(bad))


class UserStrings0141(unittest.TestCase):
    def test_no_developer_words_on_any_screen(self):
        strings = []
        for p in APP.rglob("*.xaml"):
            if "obj" in p.parts or "bin" in p.parts:
                continue
            strings += _xaml_strings(p.read_text(encoding="utf-8"))
        self.assertGreater(len(strings), 300)
        self.assertEqual([], _hits(strings))

    def test_no_developer_words_in_app_messages_and_catalog_keys(self):
        strings = []
        for p in APP.rglob("*.cs"):
            if {"obj", "bin"} & set(p.parts) or "Probe" in p.name or p.name in ("PlainLanguage.cs",):
                continue
            text = p.read_text(encoding="utf-8")
            if p.name == "UiText.cs":
                strings += re.findall(r'^\s*\["((?:[^"\\]|\\.)*)"\]\s*=', text, re.M)
            else:
                strings += _cs_literals(text)
        self.assertEqual([], _hits(strings))

    def test_no_developer_words_in_image_and_resource_messages_from_the_worker(self):
        strings = []
        for rel in ("vntext/image_batch.py", "vntext/image_text.py", "vntext_worker/image_tasks.py", "vntext_worker/resource_tasks.py", "vntext/renpy_extract.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            strings += re.findall(r'"((?:[^"\\\n]|\\.){8,})"', text) + re.findall(r"'((?:[^'\\\n]|\\.){8,})'", text)
        self.assertEqual([], _hits(strings))

    def test_english_screens_have_no_vietnamese_words_outside_quoted_button_names(self):
        text = (APP / "Services" / "UiText.cs").read_text(encoding="utf-8")
        bad = []
        for key, value in re.findall(r'^\s*\["((?:[^"\\]|\\.)*)"\]\s*=\s*"((?:[^"\\]|\\.)*)"', text, re.M):
            stripped = re.sub(r"“[^”]*”", "", value)
            if VI.search(stripped):
                bad.append(value[:120])
        self.assertEqual([], bad)

    def test_progress_lines_name_each_count_and_have_no_step_numbers(self):
        text = (APP / "Services" / "WorkflowStatus.cs").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"Bước \d/3")
        plain = (APP / "Services" / "PlainLanguage.cs").read_text(encoding="utf-8")
        for part in ("câu chưa dịch", "câu cần xem lại", "câu bị chặn"):
            self.assertIn(part, plain)

    def test_model_row_offers_the_install_button_and_hides_the_path(self):
        xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
        self.assertIn('x:Name="ModelInstallButton"', xaml)
        self.assertNotIn('Text="{Binding ModelFolder}"', xaml)
        self.assertIn("Cài bộ dịch", xaml)

    def test_saved_logs_are_mapped_when_shown_not_rewritten(self):
        cs = (APP / "ViewModels" / "MainViewModel.ExtractRunLog.cs").read_text(encoding="utf-8")
        self.assertIn("PlainLanguage.DisplayLogLine(line)", cs)


if __name__ == "__main__":
    unittest.main()
