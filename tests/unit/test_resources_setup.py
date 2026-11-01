import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from vntext.image_batch import run_image_batch
from vntext_worker.resource_tasks import run_resources
from tests.lib.work_paths import work_temp_dir

WORK = work_temp_dir('resource-setup-tests')


class ResourceSetupTests(unittest.TestCase):
    def test_renpy_inventory_does_not_scan_engine_artwork(self):
        from vntext.image_text import discover_images
        with TemporaryDirectory(dir=WORK) as temp:
            root=Path(temp);(root/'game').mkdir();(root/'renpy/common').mkdir(parents=True)
            (root/'game/menu.png').write_bytes(b'game-image')
            (root/'renpy/common/logo.png').write_bytes(b'engine-image')
            inventory=discover_images(root)
            self.assertEqual(inventory['image_paths'],[str(root/'game/menu.png')])

    def test_disposed_scope_history_does_not_conflict_with_one_current_registration(self):
        from tests.tools import cleanup_work_artifacts as cleanup
        with TemporaryDirectory(dir=WORK) as temp, patch.dict('os.environ', {'VNTEXT_RELEASE_TASK_ID':'release-0.1.15'}):
            root=Path(temp);scope=(root/'RELEASE_RUN/candidate-0.1.15').resolve();sha='a'*40
            record={'id':'current','path':str(scope),'lifecycle':'DISPOSABLE','kind':'release_task_scope',
                    'owner':'release-0.1.15','scope_id':'release-0.1.15','run_id':'release-0.1.15','scope_root':str(scope)}
            budget={'task_id':'release-0.1.15','limit_bytes':cleanup.RELEASE_TASK_015_BUDGET_LIMIT_BYTES,
                    'owner_approval':cleanup.RELEASE_TASK_015_BUDGET_APPROVAL,'scope_path':str(scope),'source_sha':sha}
            state={'head':sha,'dirty':False}
            document={'prospective_epoch':{'source_sha':sha,'release_task_budget':budget},
                      'artifacts':[record,{**record,'id':'old','lifecycle':'MISSING'}]}
            limit,reason,profile=cleanup._release_task_budget_profile_for_manifest(root,document,state)
            self.assertIsNone(reason);self.assertEqual(profile,'release-0.1.15')
            document['artifacts'].append({**record,'id':'competing-current'})
            self.assertEqual(cleanup._release_task_budget_profile_for_manifest(root,document,state)[1],'release_task_scope_ambiguous')

    def test_status_does_not_download_and_reports_each_failure(self):
        with TemporaryDirectory(dir=WORK) as temp, \
             patch('vntext.runtime_paths.app_data_root', return_value=Path(temp)), \
             patch('vntext.mt_ct2_model.resolve_model_dir', return_value=Path(temp)/'model'), \
             patch('vntext.mt_ct2_model.model_status', return_value={'ready':False,'message':'missing model'}), \
             patch('vntext.mt_ct2_model.ensure_model') as model_download, \
             patch('vntext.renpy_toolchain.managed_sdk', return_value=None), \
             patch('vntext.renpy_toolchain.download_and_install_managed_sdk') as sdk_download, \
             patch('vntext_worker.resource_tasks.emit_complete') as complete, \
             patch('vntext_worker.resource_tasks.emit_progress'), \
             patch('vntext_worker.resource_tasks.emit_log'):
            run_resources('resource-test', {'download':False}, lambda:False)
            model_download.assert_not_called(); sdk_download.assert_not_called()
            report=json.loads((Path(temp)/'resource-status.json').read_text(encoding='utf-8'))
            self.assertEqual([r['resource'] for r in report['resources']],['model','renpy','ocr'])
            self.assertFalse(complete.call_args.kwargs['ok'])
            self.assertIn('renpy:',complete.call_args.kwargs['error'])

    def test_cancelled_resource_setup_never_starts_a_download(self):
        with patch('vntext.renpy_toolchain.download_and_install_managed_sdk') as sdk_download:
            with self.assertRaisesRegex(ValueError,'cancelled'):
                run_resources('cancel',{'download':True},lambda:True)
            sdk_download.assert_not_called()

    def test_mixed_images_export_only_confirmed_text_and_translate_automatically(self):
        from PIL import Image, ImageDraw, ImageFont
        with TemporaryDirectory(dir=WORK) as temp:
            root=Path(temp); source=root/'source';source.mkdir()
            text=source/'text.png'; blank=source/'blank.png'
            image=Image.new('RGB',(400,100),'white');image.save(blank)
            ImageDraw.Draw(image).text((10,10),'Hello world',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32),fill='black');image.save(text)
            original={p.name:p.read_bytes() for p in source.iterdir()}
            def recognize(path,**kwargs):
                data=Path(path).read_bytes()
                return {'schema':1,'source_path':str(path),'source_sha256':hashlib.sha256(data).hexdigest(),
                        'width':400,'height':100,'regions':[] if data==original['blank.png'] else
                        [{'id':'line1','box':[5,5,350,70],'source_text':'Hello world','approved':False}]}
            with patch('vntext.image_batch.recognize_image',side_effect=recognize), \
                 patch('vntext.image_batch._translator', return_value=Mock(translate_many=lambda rows:['Xin chào thế giới'])):
                result=run_image_batch(source,root/'output')
            report=json.loads((Path(result['output'])/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['no_text'],1);self.assertEqual(report['total'],1)
            self.assertEqual(result['translated'],1)
            self.assertEqual(len(list((Path(result['output'])/'original').iterdir())),1)
            self.assertFalse(list(Path(result['output']).glob('.probe-*')))
            self.assertEqual(original,{p.name:p.read_bytes() for p in source.iterdir()})


if __name__=='__main__': unittest.main()
