import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.tools import renpy_vm_font_trial as trial
from vntext.renpy_toolchain import validate_sdk


class VmFontTrialTests(unittest.TestCase):
    def test_default_off_and_exact_owned_rollback_preserve_game(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('font-trial'))as tmp:
            game=Path(tmp);(game/'game').mkdir();source=game/'game/original.rpy';source.write_text('label start:\n    return\n')
            self.assertEqual(trial.install_trial(game)['scope'],'DISABLED')
            self.assertEqual(list((game/'game').iterdir()),[source])
            receipt=trial.install_trial(game,enabled=True)
            with self.assertRaisesRegex(ValueError,'already exists'):trial.install_trial(game,enabled=True)
            self.assertEqual(trial.rollback_trial(receipt)['status'],'PASS_EXACT_OWNED_FILES_REMOVED')
            self.assertEqual(source.read_text(),'label start:\n    return\n')

    def test_font_identity_and_foreign_bytes_refusal(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('font-trial'))as tmp:
            game=Path(tmp);(game/'game').mkdir();bad=game/'bad.ttf';bad.write_bytes(b'not the pinned font')
            with self.assertRaisesRegex(ValueError,'pinned identity'):trial.install_trial(game,enabled=True,font=bad)
            receipt=trial.install_trial(game,enabled=True);path=game/trial.PROFILE_PATH;path.write_bytes(b'foreign')
            with self.assertRaisesRegex(ValueError,'foreign'):trial.rollback_trial(receipt)
            self.assertEqual(path.read_bytes(),b'foreign')

    def test_sdk_language_only_profile_compiles_and_resets(self):
        sdk=validate_sdk(trial.ROOT/'.dev-env/tools/renpy-8.5.3')
        with tempfile.TemporaryDirectory(dir=work_temp_dir('font-trial-sdk'))as tmp:
            game=Path(tmp);(game/'game').mkdir()
            (game/'game/script.rpy').write_text('''init -2 python:
    gui.text_font = "Original.ttf"
    gui.name_text_font = "Original.ttf"
    gui.interface_text_font = "Original.ttf"
    gui.button_text_font = "Original.ttf"
    gui.choice_button_text_font = "Original.ttf"

init 1000 python:
    def _font_trial_probe():
        import json, os
        out = []
        for language in [None, "vietnamese", "French", None]:
            renpy.change_language(language, force=True)
            out.append([language, gui.text_font, gui.name_text_font, gui.interface_text_font, gui.button_text_font, gui.choice_button_text_font])
        with open(os.path.join(config.basedir, "font-cycle.json"), "w", encoding="utf-8") as receipt:
            json.dump(out, receipt)
        return False
    renpy.arguments.register_command("vntext_font_probe", _font_trial_probe)

label start:
    return
''',encoding='utf-8')
            receipt=trial.install_trial(game,enabled=True)
            process=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(game),'vntext_font_probe','--savedir',str(game/'saves')],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            actual=json.loads((game/'font-cycle.json').read_text())
            for row in actual:self.assertEqual(row[1:],[trial.FONT_PATH if row[0]=='vietnamese'else 'Original.ttf']*5)
            trial.own_generated_bytecode(receipt);self.assertTrue(trial.PROFILE_PATH+'c'in receipt['owned_files'])
            trial.rollback_trial(receipt)
