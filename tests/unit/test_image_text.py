import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont
from vntext.image_text import recognize_image, render_image, discover_images
from vntext_worker.image_tasks import run_image_worker
from tests.lib.work_paths import work_temp_dir

FONT = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts/arial.ttf"

class ImageTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_tempdir = tempfile.tempdir
        cls._managed_temp_root = work_temp_dir("image-text-tests")
        tempfile.tempdir = str(cls._managed_temp_root)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior_tempdir

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root / "source.png"
        Image.new("RGBA",(300,120),(255,255,255,255)).save(self.source)
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.document = {"schema":1,"source_path":str(self.source),"source_sha256":self.digest,"width":300,"height":120,
            "regions":[{"id":"manual-fixed","box":[10,10,280,70],"source_text":"Hello","ocr_text":"Hello","translation":"Xin chào",
            "approved":True,"flat_background_approved":True,"font_size":30,"background":"#FFFFFF","foreground":"#000000"}]}
    def render(self,document=None):
        return render_image(document or self.document,self.root/"out.png",FONT)
    def test_manual_output_is_separate_and_bounded(self):
        self.render()
        with Image.open(self.root/"out.png") as output:
            self.assertEqual(output.size,(300,120));self.assertEqual(output.mode,"RGBA")
            self.assertEqual(output.getchannel("A").getextrema(),(255,255))
            self.assertLess(output.crop((10,10,290,80)).convert("L").getextrema()[0],30)
            self.assertEqual(output.getpixel((0,0)),(255,255,255,255))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.digest)
    def test_invalid_coordinates_crop_overflow_and_float_rejected(self):
        for box in ([-1,0,10,10],[0,0,301,10],[0,0,1,0],[0,0,5.5,10],[0,0,True,10]):
            with self.subTest(box=box):
                doc=copy.deepcopy(self.document);doc['regions'][0]['box']=box
                with self.assertRaises(ValueError):self.render(doc)
                self.assertFalse((self.root/'out.png').exists())
    def test_unapproved_and_text_overflow_never_write_output(self):
        for changes in ({'approved':False},{'flat_background_approved':False},{'translation':'M'*300},{'translation':''},{'font_size':0}):
            with self.subTest(changes=changes):
                doc=copy.deepcopy(self.document);doc['regions'][0].update(changes)
                with self.assertRaises(ValueError):self.render(doc)
                self.assertFalse((self.root/'out.png').exists())
    def test_drift_and_existing_output_source_are_protected(self):
        Image.new('RGBA',(300,120),'black').save(self.source)
        with self.assertRaisesRegex(ValueError,'thay đổi'):self.render()
        sentinel=self.root/'out.png';sentinel.write_bytes(b'owner-output')
        with self.assertRaises(ValueError):self.render()
        self.assertEqual(sentinel.read_bytes(),b'owner-output')
        with self.assertRaises(ValueError):render_image(self.document,self.source,FONT)
    def test_complex_background_is_rejected(self):
        image=Image.effect_noise((300,120),70).convert('RGBA');image.save(self.source)
        self.document['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'không đủ phẳng'):self.render()
        self.assertFalse((self.root/'out.png').exists())
    def test_complex_background_can_be_explicitly_replaced(self):
        image=Image.effect_noise((300,120),70).convert('RGBA');image.putalpha(170);image.save(self.source)
        self.document['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.document['regions'][0]['replacement_background_approved']=True
        self.document['regions'][0]['flat_background_approved']=False
        self.render()
        with Image.open(self.root/'out.png') as output:
            self.assertEqual(output.getpixel((0,0))[3],170)
            self.assertEqual(output.getpixel((20,20))[3],255)
            self.assertEqual(output.getpixel((289,79))[:3],(255,255,255))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.document['source_sha256'])
    def test_transparent_glyph_is_rejected_without_clipping_new_text(self):
        image=Image.new('RGBA',(300,120),(0,0,0,0))
        ImageDraw.Draw(image).text((10,10),'OLD',font=ImageFont.truetype(str(FONT),30),fill=(0,0,0,255));image.save(self.source)
        digest=hashlib.sha256(self.source.read_bytes()).hexdigest();self.document['source_sha256']=digest
        with self.assertRaisesRegex(ValueError,'alpha trong suốt'):self.render()
        self.assertFalse((self.root/'out.png').exists());self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),digest)
    def test_transparent_glyph_replacement_keeps_alpha_and_pixels_outside_region(self):
        image=Image.new('RGBA',(300,120),(0,0,0,0))
        ImageDraw.Draw(image).text((16,18),'OLD',font=ImageFont.truetype(str(FONT),42),fill=(20,30,40,255))
        image.save(self.source)
        original=Image.open(self.source).convert('RGBA')
        self.document['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.document['regions'][0].update(box=[10,10,280,70],translation='Xin chào',approved=True,
                                           flat_background_approved=False,transparent_text_approved=True,font_size=34)
        self.render()
        with Image.open(self.root/'out.png') as rendered:
            rendered=rendered.convert('RGBA')
            self.assertEqual(rendered.size,original.size)
            for y in range(original.height):
                for x in range(original.width):
                    if not (10 <= x < 290 and 10 <= y < 80):
                        self.assertEqual(rendered.getpixel((x,y)),original.getpixel((x,y)))
            before=original.getchannel('A').crop((10,10,290,80)).tobytes()
            after=rendered.getchannel('A').crop((10,10,290,80))
            self.assertNotEqual(after.tobytes(),before)
            self.assertGreater(after.getextrema()[1],0)
            alpha_histogram=after.histogram()
            self.assertTrue(any(alpha_histogram[1:255]))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.document['source_sha256'])
    def test_transparent_region_replacement_preserves_alpha_outside(self):
        image=Image.new('RGBA',(300,120),(0,0,0,0));ImageDraw.Draw(image).rectangle((10,10,289,79),fill=(255,255,255,100));image.save(self.source)
        self.document['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.document['regions'][0]['replacement_background_approved']=True
        self.document['regions'][0]['flat_background_approved']=False
        self.render()
        with Image.open(self.root/'out.png') as output:
            self.assertEqual(output.getpixel((0,0))[3],0)
            self.assertEqual(output.getpixel((20,20))[3],255)
    def test_alpha_outside_opaque_region_is_preserved(self):
        image=Image.new('RGBA',(300,120),(255,255,255,0));ImageDraw.Draw(image).rectangle((10,10,289,79),fill='white');image.save(self.source)
        self.document['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest();self.render()
        with Image.open(self.root/'out.png') as output:self.assertEqual(output.getchannel('A').tobytes(),image.getchannel('A').tobytes())
    def test_partial_png_write_is_removed(self):
        def fail(image,handle,**kwargs):handle.write(b'partial');raise OSError('synthetic save failure')
        with patch.object(Image.Image,'save',fail):
            with self.assertRaisesRegex(OSError,'save failure'):self.render()
        self.assertFalse((self.root/'out.png').exists());self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.digest)
    def test_empty_regions_and_overlap_fail(self):
        doc=copy.deepcopy(self.document);doc['regions']=[]
        with self.assertRaises(ValueError):self.render(doc)
        doc=copy.deepcopy(self.document);doc['regions'].append(copy.deepcopy(doc['regions'][0]))
        with self.assertRaisesRegex(ValueError,'chồng nhau'):self.render(doc)
        self.assertFalse((self.root/'out.png').exists())
    def test_discovery_is_inventory_not_ocr_and_can_cancel(self):
        (self.root/'other.txt').write_text('not image');result=discover_images(self.root)
        self.assertEqual(result['image_paths'],[str(self.source)]);self.assertTrue(result['complete'])
        with self.assertRaisesRegex(ValueError,'cancelled'):discover_images(self.root,is_cancelled=lambda:True)
    def test_rpa_images_keep_container_member_identity_and_reject_container_drift(self):
        from io import BytesIO
        from tests.unit.test_renpy_archive import write_rpa
        archive_path=self.root/'images.rpa'; encoded=BytesIO();Image.new('RGBA',(40,20),(255,255,255,255)).save(encoded,format='PNG')
        content=encoded.getvalue();write_rpa(archive_path,{'game/gui/title.png':content})
        inventory=discover_images(self.root)
        reference=next(item for item in inventory['image_paths'] if item.startswith('rpa-member://'))
        def fake_ocr(source,**kwargs):
            _path,image,digest=__import__('vntext.image_text',fromlist=['_image'])._image(source)
            return {'schema':1,'source_path':str(source),'source_sha256':digest,'width':image.width,'height':image.height,
                    'backend':'fixture','confidence':None,'status':'NO_TEXT','regions':[]}
        out=self.root/'archive-review'
        with patch('vntext_worker.image_tasks.recognize_image',side_effect=fake_ocr), patch('vntext_worker.image_tasks.emit_complete') as complete:
            run_image_worker('archive','image_extract',{'src':reference,'out':str(out)},lambda:False)
        self.assertTrue(complete.call_args.kwargs['ok'])
        review=json.loads((out/'image_text.json').read_text(encoding='utf-8'))
        self.assertEqual(review['source_member_name'],'game/gui/title.png')
        self.assertEqual(review['source_member_sha256'],hashlib.sha256(content).hexdigest())
        changed=bytearray(archive_path.read_bytes());changed[34]^=1;archive_path.write_bytes(changed)
        with self.assertRaisesRegex(ValueError,'đã đổi'):
            run_image_worker('archive','image_render',{'document':review,'out':str(self.root/'changed-render'),'font_path':str(FONT)},lambda:False)
    def test_worker_render_retains_review_and_completion(self):
        with patch('vntext_worker.image_tasks.emit_complete') as complete:
            run_image_worker('image','image_render',{'document':self.document,'out':str(self.root/'render'),'font_path':str(FONT)},lambda:False)
        self.assertTrue(complete.call_args.kwargs['ok']);self.assertTrue((self.root/'render/translated.png').is_file())
        saved=json.loads((self.root/'render/image_text.json').read_text(encoding='utf-8'));self.assertEqual(saved['regions'][0]['id'],'manual-fixed')
    @unittest.skipUnless(os.name=='nt','Windows native OCR requires installed English recognizer')
    def test_native_ocr_and_no_text_status(self):
        ImageDraw.Draw(image:=Image.open(self.source)).text((10,10),'Hello world',font=ImageFont.truetype(str(FONT),30),fill='black');image.save(self.source);image.close()
        first=recognize_image(self.source);second=recognize_image(self.source)
        self.assertEqual(first['regions'][0]['source_text'],'Hello world');self.assertEqual(first['regions'][0]['id'],second['regions'][0]['id'])
        self.assertFalse(first['regions'][0]['approved']);self.assertIsNone(first['confidence']);self.assertEqual(first['status'],'REVIEW_REQUIRED')
        Image.new('RGB',(300,120),'white').save(self.source);empty=recognize_image(self.source)
        self.assertEqual(empty['status'],'NO_TEXT');self.assertEqual(empty['regions'],[])

    @unittest.skipUnless(os.name=='nt','Windows native image worker requires installed English recognizer')
    def test_real_worker_ocr_review_render_and_source_preservation(self):
        from tests.lib.worker_test_lib import start_worker, read_ready, run_task, complete_for, stop_worker
        with Image.open(self.source) as image:
            ImageDraw.Draw(image).text((10,10),'Hello world',font=ImageFont.truetype(str(FONT),30),fill='black');image.save(self.source)
        source_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
        worker=start_worker({'VNTEXT_DATA_ROOT':str(self.root/'data'),'VNTEXT_LOCALAPPDATA':str(self.root/'local')})
        try:
            ready=read_ready(worker,timeout=30);self.assertIsNone(worker.poll())
            extracted=run_task(worker,'ocr-image','image_extract',{'src':str(self.source),'out':str(self.root/'review')},timeout=90)
            self.assertTrue(complete_for(extracted,'ocr-image')['ok'],extracted)
            review=json.loads((self.root/'review/image_text.json').read_text(encoding='utf-8'))
            self.assertEqual(review['regions'][0]['source_text'],'Hello world')
            self.assertFalse(review['regions'][0]['approved'])
            region=review['regions'][0];region.update(box=[0,0,300,120],translation='Xin chào',approved=True,flat_background_approved=True,font_size=30)
            rendered=run_task(worker,'render-image','image_render',{'document':review,'out':str(self.root/'rendered'),'font_path':str(FONT)},timeout=30)
            self.assertTrue(complete_for(rendered,'render-image')['ok'],rendered)
            self.assertTrue((self.root/'rendered/translated.png').is_file())
            print(json.dumps({'ready':ready,'extract':extracted,'render':rendered},ensure_ascii=True))
        finally:stop_worker(worker)
        self.assertIsNotNone(worker.poll());self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),source_hash)
