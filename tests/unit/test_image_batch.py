import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont
from tests.lib.work_paths import work_temp_dir
from vntext.image_batch import run_image_batch, _font_path


class AutomaticImageTests(unittest.TestCase):
    def setUp(self):
        self.root=work_temp_dir('automatic-image-'+self.id().rsplit('.',1)[-1])
        self.source=self.root/'source.png'; self.package=self.root/'package'
        image=Image.new('RGBA',(400,120),'white')
        ImageDraw.Draw(image).text((15,20),'Hello world',font=ImageFont.truetype(str(_font_path()),34),fill='black')
        image.save(self.source)
        self.data=self.source.read_bytes()
        self.doc={'schema':1,'source_path':'','source_sha256':hashlib.sha256(self.data).hexdigest(),
                  'width':400,'height':120,'regions':[{'box':[10,10,300,60],'source_text':'Hello world','approved':False}]}

    def ocr(self,path,**kwargs):
        doc=copy.deepcopy(self.doc);doc['source_path']=str(path);return doc

    def run_batch(self,**kwargs):
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',return_value=Mock(translate_many=lambda text:['Xin chào thế giới'])):
            return run_image_batch(self.source,self.package,**kwargs)

    def report(self,result):
        return json.loads((Path(result['output'])/'report.json').read_text(encoding='utf-8'))

    def test_real_render_pairs_draft_preserves_source_and_outside_pixels(self):
        result=self.run_batch();report=self.report(result);item=report['items'][0]
        self.assertEqual(result['translated'],1);self.assertEqual(result['untranslated'],0)
        self.assertFalse(item['human_approved']);self.assertTrue(report['review_required'])
        self.assertEqual(self.source.read_bytes(),self.data)
        root=Path(result['output'])
        self.assertEqual((root/item['original']).read_bytes(),self.data)
        with Image.open(root/item['translated']) as output,Image.open(self.source) as original:
            self.assertEqual(output.size,original.size)
            self.assertEqual(output.crop((0,80,400,120)).tobytes(),original.crop((0,80,400,120)).tobytes())
            self.assertNotEqual(output.crop((10,10,310,70)).tobytes(),original.crop((10,10,310,70)).tobytes())

    def test_ocr_only_writes_review_without_model_or_render(self):
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',side_effect=AssertionError('translation must not run')),patch('vntext.image_batch._render_draft',side_effect=AssertionError('render must not run')):
            result=run_image_batch(self.source,self.package,sources=[str(self.source)],translate=False)
        report=self.report(result);item=report['items'][0]
        self.assertEqual(result['ocr_ready'],1)
        self.assertEqual(report['status'],'OCR_COMPLETE')
        self.assertEqual(item['status'],'OCR_READY')
        self.assertTrue((Path(result['output'])/item['ocr_result']).is_file())
        self.assertFalse(any((Path(result['output'])/'translated').iterdir()))
        self.assertEqual(self.source.read_bytes(),self.data)

    def test_ocr_only_reports_progress_once_per_successful_image(self):
        second=self.root/'second.png';second.write_bytes(self.data)
        third=self.root/'third.png';third.write_bytes(self.data)
        events=[]
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',side_effect=AssertionError('translation must not run')),patch('vntext.image_batch._render_draft',side_effect=AssertionError('render must not run')):
            result=run_image_batch(self.source,self.package,sources=[str(self.source),str(second),str(third)],translate=False,progress=events.append)
        report=self.report(result)
        self.assertEqual([(event['done'],event['total']) for event in events],[(1,3),(2,3),(3,3)])
        self.assertEqual(report['status'],'OCR_COMPLETE')
        self.assertEqual(result['ocr_ready'],3)
        self.assertEqual(result['ocr_failed'],0)
        self.assertEqual(result['untranslated'],0)

    def test_ocr_progress_carries_advisory_eta_without_machine_translation_or_render(self):
        """advisory_eta: seconds in the formatter convention, from elapsed/progress; omitted when unknown or finished."""
        second=self.root/'second.png';second.write_bytes(self.data)
        third=self.root/'third.png';third.write_bytes(self.data)
        events=[]
        clock=iter([0.0,2.0,4.0,6.0])
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',side_effect=AssertionError('translation must not run')),patch('vntext.image_batch._render_draft',side_effect=AssertionError('render must not run')),patch('vntext.image_batch.time.monotonic',side_effect=lambda:next(clock)):
            result=run_image_batch(self.source,self.package,sources=[str(self.source),str(second),str(third)],translate=False,progress=events.append)
        self.assertEqual([(event['done'],event['total']) for event in events],[(1,3),(2,3),(3,3)])
        self.assertEqual(events[0]['eta'],4.0)   # 2 s for 1 image, 2 left
        self.assertEqual(events[1]['eta'],2.0)   # 4 s for 2 images, 1 left
        self.assertNotIn('eta',events[2])        # finished: nothing left to estimate
        for event in events:
            self.assertEqual(event['step'],'OCR ảnh')
            self.assertTrue(event.get('eta',0)>=0)
        self.assertEqual(result['translated'],0)
        self.assertFalse(any((Path(result['output'])/'translated').iterdir()))

    def test_eta_is_omitted_when_elapsed_is_unknown(self):
        events=[]
        clock=iter([5.0,5.0,5.0])
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch.time.monotonic',side_effect=lambda:next(clock)):
            second=self.root/'second.png';second.write_bytes(self.data)
            run_image_batch(self.source,self.package,sources=[str(self.source),str(second)],translate=False,progress=events.append)
        self.assertNotIn('eta',events[0])

    def test_ocr_failure_emits_progress_and_partial_result(self):
        events=[]
        with patch('vntext.image_batch.recognize_image',side_effect=ValueError('OCR unavailable')),patch('vntext.image_batch._translator',side_effect=AssertionError('translation must not run')):
            result=run_image_batch(self.source,self.package,sources=[str(self.source)],translate=False,progress=events.append)
        report=self.report(result)
        self.assertEqual([(event['done'],event['total']) for event in events],[(1,1)])
        self.assertEqual(report['status'],'OCR_PARTIAL')
        self.assertEqual(result['ocr_ready'],0)
        self.assertEqual(result['ocr_failed'],1)
        self.assertEqual(result['untranslated'],1)

    def test_ocr_cancellation_reports_only_completed_attempts(self):
        second=self.root/'second.png';second.write_bytes(self.data)
        events=[]
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',side_effect=AssertionError('translation must not run')):
            result=run_image_batch(self.source,self.package,sources=[str(self.source),str(second)],translate=False,
                is_cancelled=lambda:bool(events),progress=events.append)
        report=self.report(result)
        self.assertTrue(result['cancelled'])
        self.assertEqual(report['status'],'CANCELLED')
        self.assertEqual([(event['done'],event['total']) for event in events],[(1,2)])
        self.assertEqual(result['ocr_ready'],1)
        self.assertEqual(result['ocr_failed'],0)

    def test_retry_preserves_previous_bytes_and_does_not_touch_csv(self):
        self.package.mkdir();csv=self.package/'translation.csv';csv.write_bytes(b'owner CSV')
        one=self.run_batch();before={str(p):p.read_bytes() for p in Path(one['output']).rglob('*') if p.is_file()}
        two=self.run_batch();self.assertNotEqual(one['output'],two['output'])
        for name,data in before.items(): self.assertEqual(Path(name).read_bytes(),data)
        self.assertEqual(csv.read_bytes(),b'owner CSV')

    def test_missing_model_does_not_download_or_claim_translation(self):
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',side_effect=ValueError('model missing')):
            result=run_image_batch(self.source,self.package)
        self.assertEqual(result['translated'],0)
        item=self.report(result)['items'][0];self.assertIn('model missing',item['reason'])
        self.assertEqual((Path(result['output'])/item['untranslated']).read_bytes(),self.data)
        self.assertFalse(list((Path(result['output'])/'translated').iterdir()))

    def test_ocr_failure_and_no_text_stay_original(self):
        for label in ('failed','no_text'):
            with self.subTest(label=label),patch('vntext.image_batch.recognize_image',side_effect=ValueError('OCR unavailable') if label=='failed' else lambda path,**kw:{**self.ocr(path),'regions':[]}):
                result=run_image_batch(self.source,self.package)
                self.assertEqual(result['untranslated'],1);self.assertTrue(self.report(result)['items'][0]['reason'])

    def test_complex_background_not_destroyed_or_mislabelled(self):
        Image.effect_noise((400,120),70).convert('RGBA').save(self.source)
        self.data=self.source.read_bytes();self.doc['source_sha256']=hashlib.sha256(self.data).hexdigest()
        result=self.run_batch();self.assertEqual(result['translated'],0)
        self.assertIn('Nền phức tạp',self.report(result)['items'][0]['reason'])
        self.assertEqual(self.source.read_bytes(),self.data)

    def test_duplicate_filenames_safe_and_report_maps_sources(self):
        other=self.root/'other';other.mkdir();second=other/'source.png';second.write_bytes(self.data)
        result=self.run_batch(sources=[str(self.source),str(second)])
        self.assertEqual(result['translated'],2)
        originals=[i['original'] for i in self.report(result)['items']]
        self.assertEqual(len(set(originals)),2)

    def test_cancel_preserves_report_without_claiming_unprocessed_success(self):
        result=self.run_batch(is_cancelled=lambda:True)
        self.assertTrue(result['cancelled']);self.assertEqual(self.report(result)['status'],'CANCELLED')
        self.assertEqual(result['translated'],0)

    def test_inventory_excludes_its_own_package(self):
        self.package.mkdir();(self.package/'old.png').write_bytes(self.data)
        with patch('vntext.image_batch.recognize_image',side_effect=self.ocr),patch('vntext.image_batch._translator',return_value=Mock(translate_many=lambda t:['Xin chào'])):
            result=run_image_batch(self.root,self.package)
        self.assertEqual(result['total'],1)

    def test_real_windows_ocr_and_ct2(self):
        if os.environ.get('VNTEXT_TEST_NATIVE_IMAGES')!='1': self.skipTest('explicit native OCR/model gate')
        result=run_image_batch(self.source,self.package)
        self.assertEqual(result['translated'],1,self.report(result))
        self.assertNotEqual(self.report(result)['items'][0]['regions'][0]['text'],self.report(result)['items'][0]['regions'][0]['translation'])

    def test_transparent_draft_preserves_alpha_outside_regions(self):
        image=Image.new('RGBA',(400,120),(0,0,0,0))
        ImageDraw.Draw(image).text((15,20),'Hello world',font=ImageFont.truetype(str(_font_path()),34),fill='white')
        image.save(self.source);self.data=self.source.read_bytes();self.doc['source_sha256']=hashlib.sha256(self.data).hexdigest()
        result=self.run_batch();self.assertEqual(result['translated'],1)
        item=self.report(result)['items'][0]
        with Image.open(Path(result['output'])/item['translated']) as rendered:
            self.assertEqual(rendered.getpixel((0,0))[3],0)
            self.assertGreater(rendered.getchannel('A').getextrema()[1],0)

    def test_budget_refuses_before_copying(self):
        with patch('vntext.image_batch.MAX_BATCH_BYTES',1): result=self.run_batch()
        self.assertEqual(result['translated'],0)
        self.assertFalse(list((Path(result['output'])/'original').iterdir()))
        self.assertIn('giới hạn',self.report(result)['items'][0]['reason'])

    def test_supported_archive_member_retains_identity(self):
        from tests.unit.test_renpy_archive import write_rpa
        from vntext.renpy_archive import member_reference
        archive=self.root/'images.rpa';write_rpa(archive,{'images/menu.png':self.data})
        result=self.run_batch(sources=[member_reference(archive,'images/menu.png')])
        item=self.report(result)['items'][0]
        self.assertEqual(result['translated'],1)
        self.assertEqual(item['member'],'images/menu.png')
        self.assertEqual(item['member_sha256'],hashlib.sha256(self.data).hexdigest())

    def _extract(self, batch):
        from types import SimpleNamespace
        from vntext.app_tasks import run_extract_task
        game=self.root/'fixture';(game/'game').mkdir(parents=True)
        (game/'game/script.rpy').write_text('label start:\n    e "Hello world"\n',encoding='utf-8')
        (game/'game/menu.png').write_bytes(self.data)
        def generate(_sdk,workspace,**_kwargs):
            templates=Path(workspace)/'game/tl/vietnamese';templates.mkdir(parents=True)
            (templates/'script.rpy').write_text('# game/script.rpy:2\ntranslate vietnamese fixture_line:\n\n    # e "Hello world"\n    e ""\n',encoding='utf-8')
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        completed=[]
        with patch('vntext.app_tasks._run_unity_preflight',return_value={}),patch('vntext.renpy_toolchain.managed_sdk',return_value=SimpleNamespace(version='8.5.3')),patch('vntext.renpy_toolchain.generate_empty_vietnamese_template',side_effect=generate),batch:
            run_extract_task(str(game),str(self.package),'safe','balanced',True,progress=lambda _:None,log=lambda _:None,complete=completed.append)
        return completed

    def test_extract_does_not_translate_or_render_images(self):
        image_batch=Mock(return_value={'total':1,'ocr_ready':1,'translated':0,'untranslated':0,'output':'image-ocr'})
        batch=patch('vntext.image_batch.run_image_batch', image_batch)
        completed=self._extract(batch)
        self.assertTrue(completed[0]['ok'],completed)
        self.assertTrue((self.package/'translation.csv').exists())
        image_batch.assert_called_once()
        self.assertFalse(image_batch.call_args.kwargs['translate'])
        self.assertIn('dịch ảnh ở bước Dịch',completed[0]['summary'])

    def _extract_raw(self, game, batch=None):
        from vntext.app_tasks import run_extract_task
        completed=[]
        with patch('vntext.image_batch.run_image_batch', batch or Mock(return_value={'total':0,'ocr_ready':0,'translated':0,'untranslated':0,'output':''})):
            run_extract_task(str(game),str(self.package),'safe','balanced',True,progress=lambda _:None,log=lambda _:None,complete=completed.append)
        return completed

    def test_image_only_folder_is_not_a_supported_extract_input(self):
        # Image OCR is a stage of Extract for a supported container (Unity / Ren'Py / text asset);
        # a bare folder of PNGs is refused up front instead of producing an empty package.
        game=self.root/'only-images';game.mkdir();(game/'menu.png').write_bytes(self.data)
        completed=self._extract_raw(game)
        self.assertFalse(completed[0]['ok'])
        self.assertIn('Chưa nhận diện input được hỗ trợ',completed[0]['error'])
        self.assertFalse((self.package/'translation.csv').exists())

    def test_empty_text_container_keeps_the_ocr_note_in_the_error(self):
        # Supported container whose only player-visible text is inside images: no text rows (EMPTY),
        # but the OCR result must be visible in the user-facing error, not hidden in the summary.
        game=self.root/'container';(game/'data').mkdir(parents=True);(game/'images').mkdir()
        (game/'data/build_info.json').write_text(json.dumps({'schema':1,'build':1}),encoding='utf-8')
        (game/'images/menu.png').write_bytes(self.data)
        batch=Mock(return_value={'total':3,'ocr_ready':2,'translated':0,'untranslated':1,'output':'image-ocr'})
        completed=self._extract_raw(game,batch)
        self.assertFalse(completed[0]['ok'])
        self.assertEqual(completed[0]['extract_status'],'EMPTY')
        self.assertIn('Không có text sử dụng được',completed[0]['error'])
        self.assertIn('OCR được 2/3 ảnh',completed[0]['error'])
        self.assertFalse(batch.call_args.kwargs['translate'])

    def test_real_worker_image_retry_protocol_twice(self):
        if os.environ.get('VNTEXT_TEST_NATIVE_IMAGES')!='1': self.skipTest('explicit native OCR/model gate')
        from tests.lib.worker_test_lib import start_worker,read_ready,run_task,complete_for,stop_worker
        proc=start_worker();self.addCleanup(stop_worker,proc);read_ready(proc)
        for task_id in ('first-image','retry-image'):
            events=run_task(proc,task_id,'image_batch',{'src':str(self.source),'out':str(self.package)},timeout=90)
            self.assertTrue(complete_for(events,task_id)['ok'],events)
        reports=list((self.package/'images').rglob('report.json'))
        self.assertEqual(len(reports),2)
        for report in reports:
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['translated'],1)
            self.assertTrue((report.parent/'ket-qua.txt').is_file())

    def test_progress_error_leaves_partial_report(self):
        def fail(_):raise RuntimeError('progress failed')
        with self.assertRaisesRegex(RuntimeError,'progress failed'):
            self.run_batch(progress=fail)
        report=json.loads((self.package/'images/report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['status'],'PARTIAL')


if __name__=='__main__':unittest.main()
