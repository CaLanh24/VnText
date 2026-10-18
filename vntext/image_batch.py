"""Automatic, unapproved image drafts; never changes source images or CSV."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from vntext.image_text import _regular, _image, _box, discover_images, recognize_image

MAX_BATCH_BYTES = 512 * 1024 * 1024
MAX_BATCH_PIXELS_BYTES = 16_000_000 * 4 + 1024 * 1024


def _translator():
    from vntext.mt_ct2_model import ensure_model, get_translator, resolve_model_dir
    return get_translator(ensure_model(resolve_model_dir(), download=False))


def _font_path():
    return Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts/arial.ttf'


def _render_draft(document, output, font_path, is_cancelled):
    """Infer appearance without forging manual approval flags."""
    from collections import Counter
    from PIL import Image, ImageDraw, ImageFont
    source, image, digest = _image(document['source_path'])
    if digest != document['source_sha256'] or image.size != (document['width'], document['height']):
        raise ValueError('Ảnh nguồn đã thay đổi trong khi OCR.')
    draw = ImageDraw.Draw(image)
    used = []
    for region in document['regions']:
        if is_cancelled():
            raise InterruptedError('cancelled')
        x,y,w,h = _box(region['box'], image.size)
        if w*h > 1_000_000:
            raise ValueError('Vùng OCR quá lớn để dựng ảnh tự động.')
        if any(x<a+c and a<x+w and y<b+d and b<y+h for a,b,c,d in used):
            raise ValueError('Các vùng OCR chồng nhau.')
        used.append((x,y,w,h))
        crop = image.crop((x,y,x+w,y+h))
        alpha = crop.getchannel('A').getextrema()
        pixels = list(crop.get_flattened_data() if hasattr(crop,'get_flattened_data') else crop.getdata())
        transparent = alpha[0] == 0 and alpha[1] > 0
        bg,count = Counter(p[:3] for p in pixels).most_common(1)[0]
        flat = sum(max(abs(a-b) for a,b in zip(p[:3],bg))<=8 for p in pixels)/(w*h)
        # OCR boxes are tight around glyphs: a flat background may occupy only
        # half the crop. Random/textured artwork has no dominant RGB cluster.
        if not transparent and (alpha[0] < 255 or flat < .50):
            raise ValueError('Nền phức tạp: chưa thể tự xóa chữ mà giữ hình nền.')
        visible = [p for p in pixels if p[3]>128]
        if not visible:
            raise ValueError('Vùng OCR không có chữ nhìn thấy.')
        fg = Counter(p[:3] for p in visible).most_common(1)[0][0] if transparent else max(visible,key=lambda p:sum((a-b)**2 for a,b in zip(p[:3],bg)))[:3]
        text = region['translation'].strip()
        if not text or len(text)>2000:
            raise ValueError('Bản dịch rỗng hoặc quá dài.')
        fitted = None
        for size in range(min(144,max(6,h)),5,-1):
            font = ImageFont.truetype(str(font_path),size)
            words = text.split(); lines=[]; line=''
            for word in words:
                candidate=(line+' '+word).strip()
                if line and draw.textbbox((0,0),candidate,font=font)[2]>w:
                    lines.append(line); line=word
                else: line=candidate
            lines.append(line); wrapped='\n'.join(lines)
            bounds=draw.multiline_textbbox((0,0),wrapped,font=font,spacing=1)
            if bounds[2]-bounds[0]<=w and bounds[3]-bounds[1]<=h:
                fitted=(font,wrapped,bounds); break
        if fitted is None:
            raise ValueError('Bản dịch không vừa vùng chữ, cần thử lại ảnh rõ/lớn hơn.')
        font,text,bounds=fitted
        draw.rectangle((x,y,x+w-1,y+h-1),fill=(0,0,0,0) if transparent else (*bg,255))
        draw.multiline_text((x-bounds[0],y-bounds[1]),text,font=font,fill=(*fg,255),spacing=1)
    output = _regular(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:
        image.save(stream,format='PNG')


def run_image_batch(source, package, *, sources=None, is_cancelled=None, progress=None):
    """Output originals and either a draft PNG or an unchanged failed copy."""
    cancelled=is_cancelled or (lambda:False)
    source=_regular(source); package=_regular(package)
    package.mkdir(parents=True,exist_ok=True)
    inventory = {'image_paths':list(sources),'complete':True,'errors':[]} if sources is not None else (
        discover_images(source, is_cancelled=cancelled, exclude_roots=(package,)) if source.is_dir() else
        {'image_paths':[str(source)] if source.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} else [],'complete':True,'errors':[]})
    if not inventory['image_paths'] and not inventory['errors']:
        return {'translated':0,'untranslated':0,'total':0,'output':'','cancelled':False}
    base=_regular(package/'images')
    root=base if not base.exists() else _regular(base/('retry-'+uuid.uuid4().hex))
    root.mkdir(parents=True,exist_ok=False)
    for name in ('original','translated','untranslated'): (root/name).mkdir()
    report={'schema':1,'status':'RUNNING','review_required':True,'inventory_complete':inventory['complete'],
            'inventory_errors':inventory['errors'],'items':[]}
    report_path=root/'report.json'
    def save():
        temp=root/'report.tmp'
        with temp.open('w',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
        temp.replace(report_path)
    save(); used_bytes=0; translator=None; model_error=''
    try:
        for index,reference in enumerate(inventory['image_paths']):
            if cancelled():
                report['status']='CANCELLED'; break
            item={'source':reference,'status':'UNTRANSLATED','reason':'','human_approved':False}
            report['items'].append(item)
            original=None
            try:
                from vntext.renpy_archive import RenPyArchive,parse_member_reference
                archive_ref=parse_member_reference(reference)
                if archive_ref:
                    container,member=archive_ref
                    content=RenPyArchive(container).read_member(member)
                    data=content['content']; filename=Path(member).name
                    item.update(container=str(container),container_sha256=content['container_sha256'],member=member,member_sha256=content['member_sha256'])
                else:
                    path=_regular(reference)
                    if path.stat().st_size>32*1024*1024: raise ValueError('Ảnh vượt 32 MiB.')
                    with path.open('rb') as stream: data=stream.read(32*1024*1024+1)
                    filename=path.name
                if len(data)>32*1024*1024: raise ValueError('Ảnh vượt 32 MiB.')
                # Reserve the maximum decoded PNG size before any output write.
                if used_bytes+len(data)*2+MAX_BATCH_PIXELS_BYTES>MAX_BATCH_BYTES:
                    raise ValueError('Đã chạm giới hạn 512 MiB cho lần xử lý ảnh này.')
                key=hashlib.sha256(reference.encode()).hexdigest()[:16]+'-'+re.sub(r'[^\w.\-]','_',filename)[:96]
                original=root/'original'/key
                with original.open('xb') as stream: stream.write(data)
                used_bytes+=len(data); item.update(original=str(original.relative_to(root)),source_sha256=hashlib.sha256(data).hexdigest())
                document=recognize_image(original,is_cancelled=cancelled)
                regions=document['regions']
                if not regions: raise ValueError('Không nhận diện được chữ tiếng Anh trong ảnh.')
                if len(regions)>500: raise ValueError('Ảnh có quá 500 vùng chữ.')
                if translator is None and not model_error:
                    try: translator=_translator()
                    except Exception as exc: model_error=str(exc)
                if model_error: raise ValueError(model_error)
                if cancelled(): raise InterruptedError('cancelled')
                translations=translator.translate_many([r['source_text'] for r in regions])
                if len(translations)!=len(regions): raise ValueError('Số dòng bản dịch không khớp OCR.')
                for region,text in zip(regions,translations):
                    if not isinstance(text,str) or not text.strip() or text.strip().casefold()==region['source_text'].strip().casefold():
                        raise ValueError('Model chưa dịch được đầy đủ chữ trong ảnh.')
                    region['translation']=text
                target=(root/'translated'/key).with_suffix('.png')
                _render_draft(document,target,_font_path(),cancelled)
                if used_bytes+target.stat().st_size>MAX_BATCH_BYTES:
                    target.unlink(); raise ValueError('Output ảnh vượt giới hạn 512 MiB.')
                used_bytes+=target.stat().st_size
                item.update(status='TRANSLATED_DRAFT',translated=str(target.relative_to(root)),translated_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),regions=[{'box':r['box'],'text':r['source_text'],'translation':r['translation']} for r in regions])
            except Exception as exc:
                item['reason']=str(exc)[:1000]
                if original is not None and original.exists():
                    unchanged=root/'untranslated'/original.name
                    with original.open('rb') as src,unchanged.open('xb') as dst: shutil.copyfileobj(src,dst)
                    used_bytes+=unchanged.stat().st_size; item['untranslated']=str(unchanged.relative_to(root))
                if cancelled(): report['status']='CANCELLED'
            finally: save()
            if progress: progress({'done':index+1,'total':len(inventory['image_paths']),'step':'Dịch ảnh','item':Path(reference).name})
        if report['status']=='RUNNING': report['status']='COMPLETE' if inventory['complete'] else 'PARTIAL'
    except Exception:
        report['status']='CANCELLED' if cancelled() else 'PARTIAL'
        raise
    finally:
        report['translated']=sum(i['status']=='TRANSLATED_DRAFT' for i in report['items'])
        report['untranslated']=len(report['items'])-report['translated']
        report['total']=len(inventory['image_paths']); save()
        lines=['KẾT QUẢ DỊCH ẢNH',
               f"Đã tạo {report['translated']} ảnh dịch nháp; {report['untranslated']} ảnh chưa dịch.",
               'original: ảnh gốc. translated: ảnh dịch tự động, cần tự xem lại. untranslated: ảnh chưa dịch, giữ nguyên nội dung.',
               'Ảnh nguồn và game không bị sửa. Để thử lại, chọn ảnh gốc bằng nút Dịch lại ảnh… trong app.',
               f"Trạng thái: {report['status']}. Chưa xử lý: {report['total']-len(report['items'])}.",'']
        lines.extend(f"{Path(item['source']).name}: {'Đã dịch nháp' if item['status']=='TRANSLATED_DRAFT' else 'Chưa dịch — '+item['reason']}" for item in report['items'])
        (root/'ket-qua.txt').write_text('\n'.join(lines),encoding='utf-8')
    return {k:report[k] for k in ('translated','untranslated','total')}|{'output':str(root),'cancelled':report['status']=='CANCELLED'}
