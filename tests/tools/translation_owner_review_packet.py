"""Prepare/verify a non-importable Owner review packet; no inference or approval."""
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'evaluation/translation_owner_review_v1'
DATASET=ROOT/'evaluation/translation_quality_phase1/dataset.v1.json'
# Human-facing proposals, never loaded by product code. All need Owner review.
PROPOSALS={
 'IDI-001':('Mara suýt để lộ bí mật về điều bất ngờ ấy.','spill the beans = để lộ bí mật; nearly chỉ suýt, chưa xác nhận đã lộ.'),
 'IDI-004':('Đến ngôi làng tiếp theo, chúng ta có thể nghỉ thôi.','call it a day = dừng công việc/chặng đi hôm nay; không phải đặt tên một ngày. Không thêm kế hoạch ngày mai.'),
 'IDI-005':('Với Lin, câu đố đầu tiên dễ như ăn kẹo.','piece of cake = rất dễ; giữ tên Lin, không tự gán giới tính.'),
 'IDI-006':('Câu đố tiếp theo khiến cô ấy phải cắn răng xin gợi ý.','bite the bullet = chấp nhận làm việc khó/ngại; her cho phép cô ấy. Xin duyệt sắc thái cắn răng.'),
 'IDI-007':('Tôi thấy trong người không khỏe sau khi đứng dưới mưa lạnh.','under the weather = không khỏe; không tự chẩn đoán bệnh cụ thể.'),
 'IDI-010':('Dù vậy, việc sửa nó vẫn tốn một khoản tiền rất lớn.','an arm and a leg = rất tốn tiền; its giữ liên hệ vật ở câu cùng cảnh, không tự đổi vật.'),
 'IDI-012':('Tôi sẽ còn hoài nghi lời hứa đó cho đến khi việc sửa chữa hoàn tất.','grain of salt = chưa hoàn toàn tin; giữ mốc until, không khẳng định lời hứa chắc chắn sai.'),
 'IDI-015':('Xin đừng để lộ bí mật trước sinh nhật của cô ấy.','let the cat out of the bag = để lộ bí mật; giữ phủ định và before.'),
 'IDI-016':('Bệnh nhân đã qua cơn nguy hiểm sau khi hạ sốt.','out of the woods trong ngữ cảnh sốt = hết nguy hiểm; không khẳng định đã khỏi bệnh hoàn toàn.'),
 'IDI-017':('Máng xối bị tràn vì ngoài trời đang mưa như trút nước.','raining cats and dogs = mưa rất to; giữ quan hệ vì và địa điểm ngoài trời.'),
 'ADDR-008':('Ngay khi trở lại, tôi sẽ gửi trang đã chỉnh sửa.','Nhân viên nói với quản lý: giữ đối tượng trang đã sửa và as soon as; tôi không gán giới tính quản lý.'),
 'ADDR-014':('Em có thể nói thật với chị; chị sẽ không giận em đâu.','Metadata gốc: chị gái nói dịu dàng với em trai. Chị/em có căn cứ; giữ cho phép và sẽ không giận.'),
 'ADDR-015':('Chị em mình đã biết nhau lâu đến thế rồi, cái cớ đó không thuyết phục đâu.','Cùng chị gái/em trai ở câu trước; diễn đạt ý bác cái cớ. Không thêm mệnh lệnh hoặc biến thành chỉ nói quen lâu.'),
 'ADDR-016':('Thưa giáo sư, khi nào có thời gian, xin xem giúp trang cuối.','Học viên cao học nói kính trọng với giáo sư lớn tuổi. Giới tính UNKNOWN: tránh ông/bà/thầy/cô; không tự chọn giới tính.'),
 'TERM-001':('Bản kê khai của bản vá liệt kê mọi tệp nguồn cùng mã kiểm tra của từng tệp.','Giữ patch, manifest, mọi source file và checksum ứng với từng tệp. Mã kiểm tra là thuật ngữ đề xuất, chưa duyệt.'),
 'TERM-004':('Kết quả tìm thấy trong bộ nhớ đệm phải được kiểm tra tính hợp lệ một lần nữa trước khi dùng lại.','Nguồn dùng cache hit/it cho kết quả cache; đề xuất làm rõ kết quả, không biến validation thành đăng nhập/xác thực danh tính. Cần duyệt cách diễn đạt.'),
 'TERM-014':('Khi xuất, bản kê khai được lưu cạnh bảng dịch trong cùng một gói.','export là thao tác xuất dữ liệu, không phải thương mại; giữ beside và one package. Cần duyệt cách chuyển câu sang bị động.'),
}
TERMS=[
 ('G01','checksum','mã kiểm tra',['TERM-001'],'Giá trị kiểm tra đi kèm tệp; không tự gán thuật toán/hash mật mã.','Không áp cho dấu tick, kiểm tra thủ công hoặc mã đăng nhập.'),
 ('G02','manifest','bản kê khai',['TERM-001','TERM-014'],'Danh mục tệp/metadata trong gói hoặc bản vá.','Không áp cho manifest động từ: biểu lộ, hay ngữ cảnh vận đơn chưa được duyệt.'),
 ('G03','patch','bản vá',['TERM-001'],'Gói thay đổi phần mềm.','Không áp cho miếng vá quần áo/vùng đất/động từ chữa lành.'),
 ('G04','cache','bộ nhớ đệm',['TERM-004'],'Dữ liệu đã lưu để dùng lại trong phần mềm.','Không áp cho chỗ giấu đồ trong game; không đồng nhất với translation memory.'),
 ('G05','cache hit','tìm thấy trong bộ nhớ đệm',['TERM-004'],'Sự kiện tìm thấy dữ liệu; toàn câu dùng kết quả tìm thấy để xử lý it.','Không thay mọi hit thành tìm thấy; không dùng cụm này thay toàn câu.'),
 ('G06','export','xuất',['TERM-014'],'Thao tác tạo gói dữ liệu xuất.','Không áp cho xuất khẩu thương mại. Cấu trúc danh từ/động từ phải duyệt cả câu.'),
]


def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def make_rows(dataset,observations):
    result=[]
    for index,source in enumerate(dataset['rows']):
        key=source['id']
        if key not in PROPOSALS:continue
        target,note=PROPOSALS[key]
        boundary=source['scenario_boundary']
        context=[dict(id=r['id'],source=r['source_en']) for r in dataset['rows']
                 if r['scenario_boundary']['group_id']==boundary['group_id']]
        result.append(dict(id=key,source=source['source_en'],observed_opus=observations[key],
            proposed_translation=target,review_note=note,address_context=source.get('address_context','UNKNOWN / not supplied'),
            scenario_boundary=copy.deepcopy(boundary),same_scenario_sources=context,
            source_provenance=dict(file='evaluation/translation_quality_phase1/dataset.v1.json',json_pointer=f'/rows/{index}',rights_pointer='/provenance'),
            intended_scope=dict(package='synthetic-owner-review-v1 ONLY',file_id=boundary['file_id'],scenario_id=boundary['group_id'],source_exact=True),
            approval_status='PENDING_OWNER_REVIEW',approved=False,human_gold=False,training_eligible=False))
    return result


def validate_payload(packet,dataset):
    assert packet['status']=='PENDING_OWNER_REVIEW'
    assert packet['product_imported'] is False and packet['approved'] is False
    assert packet['dataset_canonical_sha256']==digest(canonical(dataset))
    assert packet['source_rights']==dataset['provenance']
    assert len(packet['translations'])==17 and {r['id'] for r in packet['translations']}==set(PROPOSALS)
    for row in packet['translations']:
        assert row['approval_status']=='PENDING_OWNER_REVIEW'
        assert all(row[k] is False for k in ('approved','human_gold','training_eligible'))
        index=int(row['source_provenance']['json_pointer'].split('/')[-1])
        source=dataset['rows'][index];boundary=source['scenario_boundary']
        assert row['id']==source['id'] and row['source']==source['source_en']
        assert row['scenario_boundary']==boundary
        assert row['address_context']==source.get('address_context','UNKNOWN / not supplied')
        assert row['proposed_translation']==PROPOSALS[row['id']][0]
        assert row['same_scenario_sources']==[dict(id=r['id'],source=r['source_en']) for r in dataset['rows'] if r['scenario_boundary']['group_id']==boundary['group_id']]
        assert row['intended_scope']==dict(package='synthetic-owner-review-v1 ONLY',file_id=boundary['file_id'],scenario_id=boundary['group_id'],source_exact=True)
    assert len(packet['glossary'])==6
    for term,expected in zip(packet['glossary'],TERMS):
        assert (term['id'],term['source'],term['proposed_target'],term['occurrence_ids'])==expected[:4]
        assert term['approved'] is False and term['approval_status']=='PENDING_OWNER_REVIEW'
        assert all(row_id in PROPOSALS for row_id in term['occurrence_ids'])
    return True


def build():
    if DEST.exists():raise FileExistsError(DEST)
    dataset=load(DATASET)
    raw=ROOT/'DEV_RUN/translation-quality-goal/final-headwords.json';audit=load(raw)
    observations={r['id']:r['translation'] for r in audit['arms'][0]['rows'] if r['id'] in PROPOSALS}
    packet=dict(schema_version=1,status='PENDING_OWNER_REVIEW',approved=False,product_imported=False,
        use='Owner review only; synthetic seen development examples, not production defaults, training or fresh benchmark',
        dataset_canonical_sha256=digest(canonical(dataset)),source_rights=dataset['provenance'],
        observation_provenance=dict(raw_name=raw.name,raw_sha256=digest(raw.read_bytes()),source_sha=audit['source_sha'],
                                    code_hashes=audit['code_hashes'],qualification='Historic intermediate OPUS run, no current-source inference claim'),
        translations=make_rows(dataset,observations),
        glossary=[dict(id=i,source=s,proposed_target=t,occurrence_ids=ids,domain_note=domain,exclusions=exclude,
                       approval_status='PENDING_OWNER_REVIEW',approved=False) for i,s,t,ids,domain,exclude in TERMS],
        memory_boundary_warning='Existing memory key is normalized source/import_method/context_family; same-method unique wording may fall back across context families inside package. Intended file/scenario approval is not a guaranteed hard isolation boundary. No memory file generated or imported.',
        address_policy='Use supplied address_context only; UNKNOWN gender remains unknown. Source/context provenance accompanies each proposal.')
    validate_payload(packet,dataset)
    DEST.mkdir()
    (DEST/'proposals.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['id','kind','source','proposed_translation','owner_decision','owner_revision','owner_note'])
    for row in packet['translations']:writer.writerow([row['id'],'translation',row['source'],row['proposed_translation'],'','',''])
    for term in packet['glossary']:writer.writerow([term['id'],'glossary',term['source'],term['proposed_target'],'','',''])
    (DEST/'owner-decisions.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
    text=['# Gói dịch/glossary chờ Owner duyệt','',
          '17 câu tổng hợp đã biết lỗi + 6 thuật ngữ. Tất cả **CHƯA DUYỆT**. Không inference mới, không ghi vào app/memory, không phải human gold hay cải thiện trên câu chưa thấy.',
          '', 'Duyệt từng ID (ví dụ: `Duyệt IDI-001, G01; sửa ADDR-016 thành …; từ chối G06`). Chỉ duyệt nghĩa/thuật ngữ cụ thể; không mặc nhiên duyệt triển khai, training, phạm vi toàn app hoặc giới tính chưa biết.',
          '', 'Có thể sao chép `owner-decisions.csv` để ghi quyết định; giữ bản gốc niêm phong. Các ô để trống, không có lựa chọn mặc định. Đây là phiếu review, không phải CSV import của app. `proposals.json` giữ provenance/ngữ cảnh gốc. Không tạo `.mt/translation_memory.json` hoặc bank mặc định.',
          '', 'Các câu đều do agent tạo cho dự án, lấy từ corpus đã thấy. Việc duyệt chỉ có giá trị trên đúng nguồn/ngữ cảnh/phạm vi được duyệt. Memory hiện có fallback trong cùng package, chưa bảo đảm khóa cứng theo file/cảnh; chưa tự chuyển các đề xuất này thành memory.', '']
    for row in packet['translations']:
        context='; '.join(r['id']+': '+r['source'] for r in row['same_scenario_sources'])
        text.extend([f"## {row['id']}",'',f"**Nguồn:** {row['source']}",f"\n**OPUS đã quan sát:** {row['observed_opus']}",
                     f"\n**Đề xuất:** {row['proposed_translation']}",f"\n**Cần duyệt:** {row['review_note']}",
                     f"\n**Quan hệ nhân vật (metadata gốc):** {row['address_context']}",
                     f"\n**Cùng cảnh/tài liệu:** {context}",f"\n**Phạm vi đề xuất:** `{row['scenario_boundary']['file_id']}` / `{row['scenario_boundary']['group_id']}`, đúng câu nguồn; chưa áp dụng.",''])
    text.extend(['## Thuật ngữ — đều chờ duyệt','', '| ID | Nguồn → đề xuất | Phạm vi / không áp dụng |','| --- | --- | --- |'])
    for term in packet['glossary']:text.append(f"| {term['id']} | {term['source']} → {term['proposed_target']} | {', '.join(term['occurrence_ids'])}. {term['domain_note']} {term['exclusions']} |")
    text.extend(['','Không dùng idiom như glossary thay từ toàn cục: các bản diễn đạt thành ngữ ở trên là đề xuất cả câu, có ngữ cảnh. Sau phản hồi Owner mới xác định ID được duyệt và gate tích hợp tương ứng.'])
    (DEST/'REVIEW.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    manifest=dict(schema_version=1,status='PENDING_OWNER_REVIEW',files={p.name:digest(p.read_bytes()) for p in DEST.iterdir()},
                  builder_normalized_sha256=digest(Path(__file__).read_text(encoding='utf-8').encode('utf-8')))
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=packet['status'],translations=17,terms=6,root=str(DEST))))


def verify():
    manifest=load(DEST/'manifest.json')
    assert manifest['status']=='PENDING_OWNER_REVIEW'
    assert set(manifest['files'])=={'proposals.json','owner-decisions.csv','REVIEW.md'}
    assert manifest['builder_normalized_sha256']==digest(Path(__file__).read_text(encoding='utf-8').encode('utf-8'))
    for name,value in manifest['files'].items():assert digest((DEST/name).read_bytes())==value,name
    validate_payload(load(DEST/'proposals.json'),load(DATASET))
    decisions=list(csv.DictReader((DEST/'owner-decisions.csv').read_text(encoding='utf-8-sig').splitlines()))
    assert len(decisions)==23 and all(not r[k] for r in decisions for k in ('owner_decision','owner_revision','owner_note'))
    print('PASS: 17 proposals / 6 glossary candidates; all pending; no product import or semantic approval.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','verify'])
    {'build':build,'verify':verify}[parser.parse_args().action]()
