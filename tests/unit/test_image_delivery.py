import hashlib
import json
import os
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_archive import write_rpa
from vntext import image_delivery as delivery
from vntext.renpy_toolchain import validate_sdk

SDK = Path(os.environ.get('VNTEXT_RENPY_NATIVE_SDK', str(Path(__file__).resolve().parents[2] / '.dev-env/tools/renpy-8.5.3')))


class ImageDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = work_temp_dir('image-delivery')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'source'
        self.source = self.game / 'game/images/background.png'
        self.source.parent.mkdir(parents=True)
        Image.new('RGBA', (100,100), 'white').save(self.source)
        self.rendered = self.root / 'rendered.png'
        Image.new('RGBA', (100,100), 'blue').save(self.rendered)
        self.document = {'source_path':str(self.source), 'source_sha256':delivery._hash(self.source)}
        self.copy = self.root / 'copy'
        self.package = self.root / 'package'
        self.transaction = self.root / 'transaction'

    def prepare(self):
        result = delivery.prepare_image_delivery(self.document,self.rendered,self.game,self.package)
        shutil.copytree(self.game,self.copy)
        return result

    def test_loose_install_readback_and_restore_preserve_original(self):
        manifest = self.prepare()
        original = self.source.read_bytes()
        result = delivery.install_image_delivery(self.package,self.copy,self.transaction)
        target = Path(result['target'])
        self.assertEqual(result['status'],'READ_BACK_VERIFIED')
        self.assertEqual(delivery._hash(target),manifest['sha256'])
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual((self.copy/'game/images/background.png').read_bytes(),original)
        self.assertEqual(delivery.rollback_image_delivery(self.transaction)['status'],'ROLLED_BACK')
        self.assertFalse(target.exists())

    def test_archive_overlay_preserves_archive_and_requires_exact_baseline(self):
        archive = self.game/'game/images.rpa'
        content = self.source.read_bytes()
        write_rpa(archive,{'images/background.png':content})
        self.source.unlink()
        extracted = self.root/'extracted.png'; extracted.write_bytes(content)
        self.document.update(source_path=str(extracted),source_container_path=str(archive),
            source_container_sha256=delivery._hash(archive),source_member_name='images/background.png',
            source_member_sha256=hashlib.sha256(content).hexdigest())
        self.prepare()
        result=delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertTrue(Path(result['target']).is_file())
        self.assertEqual(delivery._hash(archive),delivery._hash(self.copy/'game/images.rpa'))
        delivery.rollback_image_delivery(self.transaction)

    def test_payload_tamper_baseline_drift_and_source_install_rejected(self):
        self.prepare()
        with self.assertRaises(ValueError): delivery.install_image_delivery(self.package,self.game,self.transaction)
        (self.copy/'game/images/background.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'baseline'): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        (self.copy/'game/images/background.png').write_bytes(self.source.read_bytes())
        Image.new('RGBA',(100,100),'red').save(self.package/'image.png')
        with self.assertRaisesRegex(ValueError,'tampered'): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertFalse(self.transaction.exists())

    def test_existing_locale_and_user_edits_are_never_overwritten(self):
        manifest=self.prepare();target=self.copy/manifest['target']
        target.parent.mkdir(parents=True);target.write_bytes(b'owner')
        with self.assertRaisesRegex(ValueError,'Existing'): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertEqual(target.read_bytes(),b'owner');target.unlink()
        delivery.install_image_delivery(self.package,self.copy,self.transaction)
        target.write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError,'preserves user edits'): delivery.rollback_image_delivery(self.transaction)
        self.assertEqual(target.read_bytes(),b'user edit')

    def test_journal_write_failure_rolls_back_published_image(self):
        manifest=self.prepare();save=delivery._save
        def fail(path,value):
            if path.name=='applied.json': raise OSError('injected receipt failure')
            return save(path,value)
        with patch.object(delivery,'_save',side_effect=fail):
            with self.assertRaises(OSError): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertFalse((self.copy/manifest['target']).exists())
        self.assertTrue((self.transaction/'intent.json').is_file())

    def test_interrupted_after_publish_can_recover_from_intent(self):
        manifest=self.prepare();save=delivery._save
        def interrupt(path,value):
            if path.name=='applied.json': raise KeyboardInterrupt()
            return save(path,value)
        with patch.object(delivery,'_save',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertTrue((self.copy/manifest['target']).exists())
        delivery.rollback_image_delivery(self.transaction)
        self.assertFalse((self.copy/manifest['target']).exists())

    def test_manifest_path_traversal_and_script_targets_rejected(self):
        self.prepare();path=self.package/'image_delivery.json';original=json.loads(path.read_text())
        for value in ['../owner.png','x\\owner.png','script.rpy','tl/vietnamese/owner.png']:
            with self.subTest(value=value):
                data=dict(original,relative_image=value,target='game/tl/vietnamese/'+value)
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): delivery.install_image_delivery(self.package,self.copy,self.transaction)
        self.assertFalse(self.transaction.exists())

    @unittest.skipUnless((SDK/'renpy.py').is_file(), 'Official pinned RenPy8.5.3 SDK absent; native loader acceptance not run')
    def test_native_loader_reads_locale_and_original_after_rollback(self):
        sdk = validate_sdk(SDK)
        original = self.source.read_bytes()
        archive = self.game/'game/images.rpa'
        write_rpa(archive, {'images/background.png':original})
        # The same native probe covers the loose file, then the archive after removing the generated loose fixture.
        self.prepare()
        result = delivery.install_image_delivery(self.package,self.copy,self.transaction)
        script = self.copy/'game/script.rpy'
        script.write_text('init 999 python:\n'
            '    import hashlib, json, os\n'
            '    renpy.game.preferences.language = "vietnamese"\n'
            '    with renpy.loader.load("images/background.png") as image_file:\n'
            '        image_digest = hashlib.sha256(image_file.read()).hexdigest()\n'
            '    with open(os.path.join(config.basedir, "native-readback.json"), "w") as receipt:\n'
            '        json.dump({"sha256": image_digest, "language": renpy.game.preferences.language}, receipt)\n'
            'label start:\n    return\n',encoding='utf-8')
        def readback(expected):
            receipt = self.copy/'native-readback.json'
            if receipt.exists(): receipt.unlink()
            command = [str(sdk.python),str(sdk.renpy_py),str(self.copy),'lint']
            run = subprocess.run(command,cwd=sdk.root,text=True,capture_output=True,timeout=120)
            print(json.dumps({'command':command,'stdout':run.stdout,'stderr':run.stderr,'exit_code':run.returncode},ensure_ascii=True))
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            self.assertTrue(receipt.is_file(), 'Native init did not produce a receipt')
            self.assertEqual(json.loads(receipt.read_text())['sha256'],expected)
        translated = delivery._hash(Path(result['target']))
        readback(translated)
        (self.copy/'game/images/background.png').unlink()
        readback(translated)
        delivery.rollback_image_delivery(self.transaction)
        readback(hashlib.sha256(original).hexdigest())
        self.assertEqual(self.source.read_bytes(),original)
