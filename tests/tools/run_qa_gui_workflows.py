"""Run with an independent full Python/Qt/Tk runtime under _work, never DEV Python."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]
from work_paths import assert_artifact_under_work, work_temp_dir

assert_artifact_under_work(Path(sys.prefix), "QA GUI Python")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["TEMP"] = os.environ["TMP"] = str(work_temp_dir("gui"))
import tempfile
tempfile.tempdir = os.environ["TEMP"]
# Read-only backend dependencies, AFTER the isolated runtime's complete Qt.
sys.path.append(str(ROOT / ".dev-env/.venv/Lib/site-packages"))
from PySide6.QtWidgets import QApplication
import PySide6
import tkinter
print("PYTHON", sys.executable, "QT", PySide6.__version__, PySide6.__file__, flush=True)
probe = tkinter.Tk()
print("TCL", probe.tk.eval("info patchlevel"), probe.tk.eval("info library"), flush=True)
probe.destroy()
suite = unittest.TestSuite()
for pattern in ("test_qt_app_workflow.py", "test_ui_app_workflow.py"):
    suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / "tests/unit"), pattern=pattern))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 2 and not result.skipped else 1)
