"""Automatic, unapproved image drafts; never changes source images or CSV."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

from vntext.image_text import _regular, _image, _box, discover_images, recognize_image

MAX_BATCH_BYTES = 512 * 1024 * 1024
MAX_BATCH_PIXELS_BYTES = 16_000_000 * 4 + 1024 * 1024


def cached_image_report(package):
    """Newest bounded report; no image discovery or OCR is performed here."""
    base = _regular(Path(package) / 'images')
    if not base.is_dir():
        return None
    paths = [base / 'report.json']
    paths += [p / 'report.json' for p in list(base.glob('retry-*'))[:64] if p.is_dir()]
    paths = [p for p in paths if p.is_file()]
    if not paths:
        return None
    path = _regular(max(paths, key=lambda p: (p.stat().st_mtime_ns, str(p))))
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Báo cáo ảnh vượt 4 MiB.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('schema') != 1 or not isinstance(report.get('items'), list) or len(report['items']) > 100000:
        raise ValueError('Báo cáo ảnh không hợp lệ; hãy lấy text lại.')
    return path, report


def translate_cached_images(package, *, source=None, is_cancelled=None, progress=None):
    """Translate Extract's positive OCR results. Never scans or OCRs again and never approves a draft."""
    cached = cached_image_report(package)
    if cached is None:
        raise ValueError('Chưa có kết quả ảnh từ Lấy text; hãy lấy text trước.')
    report_path, report = cached
    root = report_path.parent
    if source is not None and Path(report.get('source_root', '')).resolve() != Path(source).resolve():
        raise ValueError('Kết quả ảnh thuộc game khác; hãy lấy text lại.')
    cancelled = is_cancelled or (lambda: False)
    translator = None
    positives = [i for i in report['items'] if i.get('text_detected')]

    def contained(relative):
        path = _regular(root / relative)
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Đường dẫn kết quả ảnh nằm ngoài gói.')
        return path

    def save():
        tmp = root / ('report-' + uuid.uuid4().hex + '.tmp')
        try:
            tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(report_path)
        finally:
            tmp.unlink(missing_ok=True)

    for index, item in enumerate(positives):
        if cancelled():
            break
        if item.get('status') == 'TRANSLATED_DRAFT':
            continue
        try:
            ocr = contained(item.get('ocr_result', ''))
            if not ocr.is_file() or ocr.stat().st_size > 4 * 1024 * 1024:
                raise ValueError('Thiếu kết quả OCR hợp lệ; hãy lấy text lại.')
            document = json.loads(ocr.read_text(encoding='utf-8'))
            original = contained(item['original'])
            _, _, digest = _image(original)
            if digest != item.get('source_sha256') or digest != document.get('source_sha256'):
                raise ValueError('Ảnh nguồn đã đổi; hãy lấy text lại.')
            if Path(document.get('source_path', '')).resolve() != original.resolve():
                raise ValueError('OCR không khớp ảnh trong gói.')
            regions = document.get('regions')
            if not isinstance(regions, list) or not regions or len(regions) > 500:
                raise ValueError('Vùng OCR không hợp lệ.')
            if translator is None:
                translator = _translator()
            values = translate_region_texts(translator, [r['source_text'] for r in regions])
            if len(values) != len(regions):
                raise ValueError('Số dòng bản dịch không khớp OCR.')
            for region, value in zip(regions, values):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('Model chưa tạo được bản dịch.')
                region['translation'] = value
                region['approved'] = False
            if cancelled():
                break
            target = contained('translated/' + uuid.uuid4().hex + '.png')
            _render_draft(document, target, _font_path(), cancelled)
            tmp = ocr.with_name(ocr.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                tmp.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
                tmp.replace(ocr)
            finally:
                tmp.unlink(missing_ok=True)
            item.update(status='TRANSLATED_DRAFT', translated=str(target.relative_to(root)),
                        translated_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), reason='', human_approved=False)
        except Exception as exc:
            item.update(status='UNTRANSLATED', reason=str(exc)[:1000])
        if progress:
            progress({'done': index + 1, 'total': len(positives), 'step': 'Dịch ảnh đã OCR', 'item': Path(item['source']).name})
        save()
    report['translated'] = sum(i.get('status') == 'TRANSLATED_DRAFT' for i in positives)
    report['total'] = len(positives)
    report['untranslated'] = len(positives) - report['translated']
    report['ocr_ready'] = sum(i.get('status') == 'OCR_READY' for i in positives)
    report['status'] = 'CANCELLED' if cancelled() else 'PARTIAL' if report['untranslated'] or not report.get('inventory_complete') else 'COMPLETE'
    save()
    return {k: report[k] for k in ('translated', 'untranslated', 'total')} | {'output': str(root), 'cancelled': cancelled()}


def _translator():
    from vntext.mt_ct2_model import ensure_model, get_translator, resolve_model_dir
    return get_translator(ensure_model(resolve_model_dir(), download=False))


def _font_path():
    return Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts/arial.ttf'


_PROTECTED = re.compile(r'\[[^\[\]]*\]|\{[^{}]*\}|%\([A-Za-z_]\w*\)[sdif]|%[sdif]|\\n', re.IGNORECASE)   # IGNORECASE: the translation is upper-cased before its tokens are matched and restored


def _is_all_caps(text):
    """UI art is usually ALL CAPS (NEW GAME); the MT model leaves such text unchanged or mistranslates it. Placeholders/tags are not text."""
    letters = [ch for ch in _PROTECTED.sub('', text) if ch.isalpha()]
    return len(letters) >= 3 and all(ch.isupper() for ch in letters)      # 2-letter tokens (HP, MP, OK) are abbreviations, left as they are


def _sentence_case(text):
    """Lower-case the PLAIN text only (first letter capitalised); every [placeholder], {tag} and %s stays byte-identical."""
    pieces, position, first = [], 0, True
    for match in _PROTECTED.finditer(text):
        plain = text[position:match.start()].lower()
        if first and any(ch.isalpha() for ch in plain):
            plain = plain.capitalize() if plain[:1].isalpha() else plain[:1] + plain[1:].capitalize()
            first = False
        pieces += [plain, match.group(0)]
        position = match.end()
    tail = text[position:].lower()
    if first and any(ch.isalpha() for ch in tail):
        tail = tail.capitalize() if tail[:1].isalpha() else tail[:1] + tail[1:].capitalize()
    return ''.join(pieces) + tail


def _recapitalise(original, value):
    """Upper-case the translation but put the SOURCE tokens back exactly; if the model changed/dropped a token the answer is returned untouched
    so the existing downstream guards decide (no forged repair)."""
    sources = _PROTECTED.findall(original)
    upper = value.upper()
    found = _PROTECTED.findall(upper)
    if sorted(token.upper() for token in sources) != sorted(found):
        return value
    pool = list(sources)

    def restore(match):
        token = match.group(0)
        for index, candidate in enumerate(pool):
            if candidate.upper() == token:
                return pool.pop(index)
        return token
    return _PROTECTED.sub(restore, upper)


def translate_region_texts(translator, texts):
    """Translate OCR region texts; ALL-CAPS regions are translated in sentence case and the result is set back in capitals."""
    from vntext.ui_labels import resolve_ui_label_translation

    # An exact standalone menu label (Inventory, Save, Options ...) takes the curated catalog; everything else goes through the model.
    fixed = [resolve_ui_label_translation(text, "UI:image") for text in texts]
    pending = [index for index, hit in enumerate(fixed) if hit is None]
    normalized = [_sentence_case(texts[i].strip()) if _is_all_caps(texts[i]) else texts[i] for i in pending]
    translations = translator.translate_many(normalized) if pending else []
    if len(translations) != len(pending):
        return translations
    results = list(fixed)
    for index, value in zip(pending, translations):
        original = texts[index]
        results[index] = _recapitalise(original, value) if isinstance(value, str) and _is_all_caps(original) else value
    return results


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
        estimated_background = None
        if not transparent and (alpha[0] < 255 or flat < .50):
            # A separate, explicitly unapproved preview may estimate the covered
            # background from neighbouring pixels. Never call this restoration
            # of the original artwork, and never mutate the source image.
            samples=[]
            if y>0: samples.append(image.crop((x,y-1,x+w,y)).resize((w,h)))
            if y+h<image.height: samples.append(image.crop((x,y+h,x+w,y+h+1)).resize((w,h)))
            if x>0: samples.append(image.crop((x-1,y,x,y+h)).resize((w,h)))
            if x+w<image.width: samples.append(image.crop((x+w,y,x+w+1,y+h)).resize((w,h)))
            if not samples:
                raise ValueError('Vùng chữ phủ toàn ảnh; không đủ nền để dựng bản nháp an toàn.')
            estimated_background=samples[0]
            for sample in samples[1:]: estimated_background=Image.blend(estimated_background,sample,.5)
            region['automatic_background_estimate']=True
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
        if estimated_background is not None:
            image.paste(estimated_background,(x,y))
        else:
            draw.rectangle((x,y,x+w-1,y+h-1),fill=(0,0,0,0) if transparent else (*bg,255))
        draw.multiline_text((x-bounds[0],y-bounds[1]),text,font=font,fill=(*fg,255),spacing=1)
    output = _regular(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:
        image.save(stream,format='PNG')


def run_image_batch(source, package, *, sources=None, is_cancelled=None, progress=None, translate=True):
    """OCR images, optionally translating and rendering drafts for Translate."""
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
    for name in ('original','ocr','translated','untranslated'): (root/name).mkdir()
    report={'schema':1,'source_root':str(source.resolve()),'status':'RUNNING','review_required':True,'inventory_complete':inventory['complete'],
            'inventory_errors':inventory['errors'],'items':[]}
    report_path=root/'report.json'
    def save():
        temp=root/'report.tmp'
        with temp.open('w',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
        for attempt in range(8):            # Windows indexers/scanners can briefly hold the fresh file
            try:
                temp.replace(report_path); break
            except PermissionError:
                if attempt == 7: raise
                time.sleep(0.05 * (attempt + 1))
    save(); used_bytes=0; translator=None; model_error=''
    started=time.monotonic()
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
                # Decode/OCR in a temporary probe. Only confirmed text-bearing images
                # enter the exported original/translated/untranslated folders.
                original=root/('.probe-'+key)
                with original.open('xb') as stream: stream.write(data)
                used_bytes+=len(data); item.update(original=str(original.relative_to(root)),source_sha256=hashlib.sha256(data).hexdigest())
                document=recognize_image(original,is_cancelled=cancelled)
                regions=document['regions']
                if not regions:
                    item.update(status='NO_TEXT', reason='Không phát hiện chữ; không xuất ảnh.')
                    item.pop('original',None)
                    original.unlink()
                    used_bytes-=len(data)
                    original=None
                    if progress:
                        progress({'done':index+1,'total':len(inventory['image_paths']),'step':'Lọc ảnh không có chữ','item':filename})
                    continue
                if len(regions)>500: raise ValueError('Ảnh có quá 500 vùng chữ.')
                confirmed=root/'original'/key
                original.replace(confirmed)
                original=confirmed
                document['source_path']=str(original)
                if item.get('container'):
                    document.update(source_container_path=item['container'], source_container_sha256=item['container_sha256'],
                                    source_member_name=item['member'], source_member_sha256=item['member_sha256'])
                else:
                    document['source_reference']=reference
                item.update(original=str(original.relative_to(root)),text_detected=True)
                if not translate:
                    ocr_path=(root/'ocr'/key).with_suffix('.json')
                    with ocr_path.open('x',encoding='utf-8') as stream:
                        json.dump(document,stream,ensure_ascii=False,indent=2)
                    item.update(status='OCR_READY',ocr_result=str(ocr_path.relative_to(root)),regions=[{'box':r['box'],'text':r['source_text']} for r in regions])
                else:
                    if translator is None and not model_error:
                        try: translator=_translator()
                        except Exception as exc: model_error=str(exc)
                    if model_error: raise ValueError(model_error)
                    if cancelled(): raise InterruptedError('cancelled')
                    translations=translate_region_texts(translator,[r['source_text'] for r in regions])
                    if len(translations)!=len(regions): raise ValueError('Số dòng bản dịch không khớp OCR.')
                    for region,text in zip(regions,translations):
                        if not isinstance(text,str) or not text.strip() or text.strip().casefold()==region['source_text'].strip().casefold():
                            raise ValueError('Model chưa dịch được đầy đủ chữ trong ảnh.')
                        region['translation']=text
                    ocr_path=(root/'ocr'/key).with_suffix('.json')
                    target=(root/'translated'/key).with_suffix('.png')
                    _render_draft(document,target,_font_path(),cancelled)
                    with ocr_path.open('x',encoding='utf-8') as stream:
                        json.dump(document,stream,ensure_ascii=False,indent=2)
                    item['ocr_result']=str(ocr_path.relative_to(root))
                    item['background_estimated']=any(r.get('automatic_background_estimate') for r in regions)
                    if used_bytes+target.stat().st_size>MAX_BATCH_BYTES:
                        target.unlink(); raise ValueError('Output ảnh vượt giới hạn 512 MiB.')
                    used_bytes+=target.stat().st_size
                    item.update(status='TRANSLATED_DRAFT',translated=str(target.relative_to(root)),translated_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),regions=[{'box':r['box'],'text':r['source_text'],'translation':r['translation']} for r in regions])
            except Exception as exc:
                item['reason']=str(exc)[:1000]
                if item.get('text_detected') and original is not None and original.exists():
                    unchanged=root/'untranslated'/original.name
                    with original.open('rb') as src,unchanged.open('xb') as dst: shutil.copyfileobj(src,dst)
                    used_bytes+=unchanged.stat().st_size; item['untranslated']=str(unchanged.relative_to(root))
                if cancelled(): report['status']='CANCELLED'
            finally:
                if original is not None and original.name.startswith('.probe-'):
                    original.unlink(missing_ok=True)
                    item.pop('original',None)
                save()
            if progress:
                event={'done':index+1,'total':len(inventory['image_paths']),'step':'Dịch ảnh' if translate else 'OCR ảnh','item':Path(reference).name}
                # Advisory ETA (seconds, the convention of the other stages): elapsed/done * remaining; omitted while unknown or finished.
                elapsed=time.monotonic()-started;remaining=event['total']-event['done']
                if remaining>0 and elapsed>0: event['eta']=round(elapsed/event['done']*remaining,1)
                progress(event)
        if report['status']=='RUNNING':
            failed=any(item['status']=='UNTRANSLATED' for item in report['items'])
            complete=inventory['complete'] and not failed
            report['status']=('OCR_COMPLETE' if complete else 'OCR_PARTIAL') if not translate else ('COMPLETE' if complete else 'PARTIAL')
    except Exception:
        report['status']='CANCELLED' if cancelled() else 'PARTIAL'
        raise
    finally:
        report['translated']=sum(i['status']=='TRANSLATED_DRAFT' for i in report['items'])
        report['ocr_ready']=sum(i['status']=='OCR_READY' for i in report['items'])
        report['ocr_failed']=sum(i['status']=='UNTRANSLATED' for i in report['items']) if not translate else 0
        report['untranslated']=report['ocr_failed'] if not translate else sum(i['status']=='UNTRANSLATED' for i in report['items'])
        report['scanned']=len(report['items'])
        report['no_text']=sum(i['status']=='NO_TEXT' for i in report['items'])
        report['total']=sum(bool(i.get('text_detected')) for i in report['items'])
        report['candidates']=len(inventory['image_paths'])
        save()
        if translate:
            lines=['KẾT QUẢ DỊCH ẢNH',
                   f"Đã tạo {report['translated']} ảnh dịch nháp; {report['untranslated']} ảnh chưa dịch.",
                   'original: ảnh gốc. translated: ảnh dịch tự động, cần tự xem lại. untranslated: ảnh chưa dịch, giữ nguyên nội dung.',
                   'Ảnh nguồn và game không bị sửa. Để thử lại, chọn ảnh gốc bằng nút Dịch ảnh… trong bước Dịch.',
                   f"Trạng thái: {report['status']}. Chưa xử lý: {report['total']-len(report['items'])}.",'']
            lines.extend(f"{Path(item['source']).name}: {'Đã dịch nháp' if item['status']=='TRANSLATED_DRAFT' else 'Chưa dịch — '+item['reason']}" for item in report['items'])
        else:
            lines=['KẾT QUẢ OCR ẢNH',
                   f"Đã OCR {report['ocr_ready']} ảnh; OCR lỗi/chưa nhận diện được chữ ở {report['ocr_failed']} ảnh.",
                   'Ảnh gốc được giữ nguyên. Không chạy dịch máy hoặc render trong bước Lấy text.',
                   f"Trạng thái: {report['status']}. Chưa xử lý: {report['total']-len(report['items'])}.",'']
            lines.extend(f"{Path(item['source']).name}: {'OCR sẵn sàng' if item['status']=='OCR_READY' else 'OCR chưa xong — '+item['reason']}" for item in report['items'])
        (root/'ket-qua.txt').write_text('\n'.join(lines),encoding='utf-8')
    return {k:report[k] for k in ('translated','untranslated','total','ocr_ready','ocr_failed')}|{'output':str(root),'cancelled':report['status']=='CANCELLED'}
