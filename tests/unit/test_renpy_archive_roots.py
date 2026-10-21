"""Raw RPA members and resolved game script paths are distinct identities."""
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_archive import write_rpa,write_rpa2
from vntext.renpy_toolchain import copy_template_workspace,RenPyToolchainError
from vntext.app_tasks import run_extract_task
from vntext.renpy_toolchain import validate_sdk

SDK=Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3'


class RenPyArchiveRootTests(unittest.TestCase):
    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_archive_source_recovery_does_not_claim_runtime_execution(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-rpa-runtime'))as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            archive=game/'game/archive.rpa';write_rpa(archive,{'story/script.rpy':b'label archived_start:\n    "Archive dialogue"\n    return\n'})
            before=archive.read_bytes();events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'PARTIAL',events[-1])
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            entry=next(e for e in manifest['entries']if e['source_text']=='Archive dialogue')
            record=entry['native_contract']['provenance']['source_container']
            self.assertEqual(record['member_name'],'story/script.rpy')
            self.assertEqual(entry['file_path'],'game/story/script.rpy')
            self.assertFalse(record['runtime_execution_proven'])
            lookup=root/'lookup';(lookup/'game').mkdir(parents=True)
            (lookup/'game/archive.rpa').write_bytes(before)
            (lookup/'game/probe.rpy').write_text('init 1000 python:\n    import json, os\n    with open(os.path.join(config.basedir,"readback.json"),"w") as output:\n        json.dump({"loaded":renpy.has_label("archived_start")},output)\n',encoding='utf-8')
            sdk=validate_sdk(SDK)
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(lookup),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse(json.loads((lookup/'readback.json').read_text())['loaded'])
            self.assertEqual(archive.read_bytes(),before)

    def test_standard_and_legacy_members_in_nested_rpa2_and_rpa3(self):
        for writer in (write_rpa,write_rpa2):
            for raw in ('story/script.rpy','game/story/script.rpy'):
                with self.subTest(writer=writer.__name__,raw=raw),tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-rpa-roots'))as tmp:
                    root=Path(tmp);game=root/'source';(game/'game/archives').mkdir(parents=True)
                    archive=game/'game/archives/script.rpa';content=b'label start:\n    "Archive dialogue"\n    return\n'
                    writer(archive,{raw:content});before=archive.read_bytes()
                    inventory=copy_template_workspace(game,root/'workspace',translation_only=True)
                    self.assertEqual((root/'workspace/game/story/script.rpy').read_bytes(),content)
                    record=inventory['archive_sources']['game/story/script.rpy']
                    self.assertEqual(record['member_name'],raw)
                    self.assertEqual(record['resolved_game_path'],'game/story/script.rpy')
                    self.assertEqual(record['member_sha256'],hashlib.sha256(content).hexdigest())
                    self.assertEqual(archive.read_bytes(),before)

    def test_standard_and_legacy_collision_refuses_before_copy(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-rpa-collision'))as tmp:
            root=Path(tmp);game=root/'source';(game/'game/nested').mkdir(parents=True)
            write_rpa(game/'game/a.rpa',{'story/script.rpy':b'label a:\n    "A"\n'})
            write_rpa2(game/'game/nested/b.rpa',{'game/story/script.rpy':b'label b:\n    "B"\n'})
            with self.assertRaisesRegex(RenPyToolchainError,'collid'):
                copy_template_workspace(game,root/'workspace',translation_only=True)
            self.assertFalse((root/'workspace').exists())
