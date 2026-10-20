# Lộ trình chất lượng dịch 0 đồng

**M1–M4 đã được Owner giao thực thi/bàn giao2026-10-20:**
[packet](../evaluation/translation_silver_packet_v1/README.md)60curation rows,
12audited IDs,48term audits,3term candidates/9memory candidates. Focused4tests
PASS/cleanupPASS,0newmodelrun. Chi tiết canonical plan/handoff. Bên dưới là
thiết kế/budget đã duyệt, không còn chờ quyền cho M1–M4.

Ngày kiểm: **2026-10-20, Asia/Tokyo**. Owner chốt **ngân sách phát sinh0đ**:
không thuê reviewer/GPU/máy, mua phần cứng, trial cần thẻ/đặt cọc/autocharge.
Phương án trả phí đang soạn đã hủy trước commit; không phát sinh giao dịch.
Quy tắc này thay gợi ý xin budget trả phí trong plan lịch sử.

**Không thuê máy vẫn khép được phần nghiên cứu của plan.** Bước1–3 đã có kết quả;
có thể bàn giao dữ liệu/evidence và kết luận giữ OPUS bằng tài nguyên đã có.
Bước4 vốn là huấn luyện có điều kiện, ghi **NOT_TRIGGERED / DEFERRED** khi thiếu
corpus được người duyệt/compute phù hợp. Không gọi training đã hoàn thành;
không coi chưa chi tiền là lý do cả plan không thể khép.

## Một đường đi: gói silver và chính sách tái sử dụng evidence hiện có

Tái sử dụng **60 nguồn synthetic Phase19** và raw OPUS/Hy/review đã tồn tại,
không tạo benchmark/prompt/model mới. Sáu nhóm hội thoại, thành ngữ, xưng hô,
UI, thuật ngữ, protected tokens mỗi nhóm10. Toàn bộ đã xem: chỉ development/
regression. Chọn vì có source/context/provenance và separate-agent blind review
trước đây; không dùng dữ liệu game/CSV riêng/user. Mục tiêu là gói dữ liệu truy
nguyên được, phân loại trường hợp tái sử dụng và lỗi cần giữ, không hứa model
tốt hơn chỉ nhờ đóng gói dữ liệu.

| Mốc0đ | Deliverable đề nghị sau khi được giao thực thi | Budget/điểm dừng |
| --- | --- | --- |
| M1. Quyền và identity | Manifest60 source IDs/dataset SHA/quyền synthetic, source SHA/script/hash từng run và raw-output/review pointers; giữ original labels, không copy model/log lớn. | DEV<=1h offline. Thiếu quyền/hash/source ghi UNKNOWN, loại khỏi tập tái sử dụng. |
| M2. Curate có giới hạn | Bảng60 dòng: source/context, OPUS/Hy gốc, agent review cũ, retain/reject/uncertain và nhóm lỗi. DEV đối chiếu tối đa12 major/uncertain đã ghi, không sửa output để tăng điểm. | DEV<=2h; Brain read-only audit mẫu12 dòng/mapping/severity<=1h. Không child/reviewer agent mới. Hết giờ bàn giao số thực/unresolved, không mở phase mới. |
| M3. Glossary/memory candidate | Audit bank48 terms hiện có theo domain/counter-sense; chọn tối đa12 entries đủ evidence làm candidate bank. Memory candidate tối đa20 exact-source/context pairs, có origin/reviewer-status. Không đủ giữ ít hơn/rỗng có reason. | DEV<=1h. Tất cả silver/needs-human-review; không ghi vào glossary/memory/cache sản phẩm hoặc gọi là approved. |
| M4. Bàn giao và đóng | Manifest+review table+candidate bank/memory+receipt, ma trận4bước/limitations/cleanup. Brain kiểm traceability/labels/boundary, không semantic human sign-off. | DEV<=1h; **tổng DEV<=5h, Brain<=1h**, không mua agent/API credits. Hết budget đóng đợt, không vòng prompt/benchmark sau. |

Đây là scope M1–M4 Owner đã giao thực thi; manifest60/candidate bank/memory đã
bàn giao. Một lần Owner giao là đủ, không bắt Owner dịch/duyệt
hàng trăm câu. Dùng schema/token/dedup tooling đã có khi cần; chỉ focused gate
cho thay đổi thật, không chạy lại125 test/model vì bảng tài liệu. Không inference
mới. DEV triển khai duy nhất, Brain chỉ read-only nghiệm thu; không writer thứ hai.

### Nhãn, semantic review và quyền

- `agent-draft`: nguồn/target do agent/model soạn, chưa review.
- `agent-reviewed silver`: DEV đối chiếu source, Brain audit evidence; đủ tổ
  chức nghiên cứu/regression có nhãn hạn chế. **Không human gold**, không target
  training đã duyệt hoặc semantic/product acceptance.
- `rejected`/`uncertain`: giữ raw/reason, không tự gắn nhãn đúng.
- `human-reviewed`: chỉ khi người EN→VI tự nguyện sẵn có thực sự kiểm cặp và ký
  review. Hiện **chưa xác định được người này**; DEV/Brain agent không thay vai
  người. Không thuê và không giao nghĩa vụ dịch cho Owner. Thiếu người thì M4
  đóng ở silver, bước4 deferred; không chờ vô thời hạn.

Domain-qualified glossary phải có counter-sense; memory chỉ exact consistency.
Candidate silver không được import vào approved memory. Phase2 đã cho thấy
lexical/glossary ablation gây lỗi; không thay route/validator để đưa candidate
vào app. Lợi ích bàn giao là traceability/giới hạn/vật liệu tái sử dụng;
**chưa đo cải thiện câu mới**. Nếu tương lai có reviewer tự nguyện thì calibration
mẫu20 synthetic trước, không mặc định mở chiến dịch300 câu.

## Không thuê máy thì bốn bước đạt gì?

| Bước | Đường0đ/evidence | Disposition |
| --- | --- | --- |
| 1. Evaluation | Frozen100 synthetic/split/rubric/actual OPUS Phase1 base10873fc; M1–M2 tái dùng60 Phase19 base685c810. | Foundation/research measured. Curation miễn phí khép ở silver; chưa independent human gold. |
| 2. Route hiện có | Phase2 base4c72525 đã so glossary/memory/ablation, bác candidate runtime và khôi phục. M3 chỉ audit/candidate từ evidence cũ. | Evaluation/recommendation hoàn tất; OPUS giữ nguyên, chưa hứa tăng chất lượng. |
| 3. Candidate context | Pinned HyQ4/runtime đã chạy thật CPU guest4GiB; Phase4/19/22 raw/review. Phase22 base228f038 còn3major/2uncertain/7acceptable; retry fixab8485b125testPASS, không quality rerun. | Nghiên cứu đã thực hiện; candidate REJECTED. Không cần thuê máy để kết luận; không prompt vô hạn/thay OPUS. |
| 4. Conditional training | Taxonomy/silver/provenance/feasibility design chuẩn bị offline được. Chưa human gold/compute verified và chưa có quyền tải/cài/cloud/training. | **NOT_TRIGGERED / DEFERRED**, không trainingPASS. Không chặn đóng M4/research plan. Chỉ mở lại khi có quyền/điều kiện miễn phí thật. |

SHA/receipt đầy đủ ở [canonical plan](TRANSLATION_QUALITY_PLAN.md), disposition
2026-10-20 và Phase1/2/4/19/22. Raw cũ không thành exact-HEAD/unseen nhờ curation.
Không teacher labels giả gold, benchmark mới hoặc nhãn held-out mới cho câu đã xem.

## Phần cứng sẵn có, model và giới hạn training

Read-only CIM guest **HIU1**2026-10-20: RAM **4.293.808.128 bytes (~4GiB)**,
4 logical processors, Intel Core Ultra7 255HX; video Microsoft Hyper-V Video và
Remote Display Adapter, AdapterRAM null. Không chứng minh guest có CUDA GPU;
**host không được kiểm**, không giả có RAM/GPU hoặc quyền dùng host. C: còn
153.594.433.536 bytes tại lúc đo nhưng không nới cap: checkout non-exempt1GiB,
shared `.dev-env`6GiB. 0đ nghĩa không phát sinh tiền/credits mua thêm; vẫn dùng
thiết bị/điện/quota thuê bao đã có, không hứa không có chi phí cơ hội.

Đã có `.dev-env/cache/models/Hy-MT2-1.8B-GGUF/Hy-MT2-1.8B-Q4_K_M.gguf`
1.133.080.448 bytes và LICENSE.txt: artifact inference, không mặc định weights
training. [Upstream tree](https://huggingface.co/tencent/Hy-MT2-1.8B/tree/main)
hiện BF16 safetensors4,08GB/repo4,09GB, revision khảo sát
`9a341cd1b679d3efd23b46e847b01745a71ed792`;
[model card](https://huggingface.co/tencent/Hy-MT2-1.8B) có Vietnamese/Transformers>=5.6.0,
[license](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/LICENSE.txt) Apache-2.0.
Training sau này cần weights, tokenizer/config và torch/CUDA/PEFT/DeepSpeed/
Transformers được pin/hash/license; **chưa tải/cài/khóa compatibility**.

[Training guide chính thức](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/train/README.md)
nêu LoRA1.8B/ZeRO-2 no-offload cần1GPU24GB+ ở seq8192. Không suy từ đó rằng mọi
cấu hình ngắn/quantized16GB đều không thể; **chưa có evidence** cho đường đó.
Không hứa CPU-only train1.8B trên4GiB. Guide còn chữ Hy3 preview; web reader chưa
đọc được requirements/launcher từ URL suy theo guide, actual entrypoint/lockfile/
remote code và peak RAM/VRAM còn UNKNOWN. Không chạy source đoán. M1–M4 không
cần weights/dependency mới hoặc GPU; không chép training stack vượt cap vào guest.

## Free notebook: cơ hội tùy chọn, không phải prerequisite đóng plan

Nguồn chính thức kiểm2026-10-20:

- [Colab FAQ](https://research.google.com/colaboratory/faq.html) xác nhận free
  compute/GPU nhưng GPU/quota/lifetime không bảo đảm; free notebook tối đa12h
  tùy usage/availability, không có12h được cấp chắc chắn. VM private theo account;
  share notebook chia cả code/output/comments.
- [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks) mô tả free P100 và
  có thể phải chờ. Không cộng VRAM nhiều GPU để gọi là mộtGPU24GB đủ upstream.

**Không chọn free-tier làm đường bắt buộc.** Nguồn đã đọc chưa xác nhận mọi điều
kiện thẻ/eligibility của account Owner; chưa có account/allocation/privacy được
kiểm. Không cam kết “không cần thẻ”/GPU24GB sẵn. Chỉ xét sau khi Owner cho kiểm
free-tier: đòi thẻ/đặt cọc/trial/paid plan/billing link/quyền dữ liệu không phù hợp
hoặc thiếu compute thì dừng. Không mua quota, nhiều account, keep-alive/bypass
notebook UI. Không tạo/login account, upload, mở runtime/tải weights trong task này.

Nếu sau này **cả** reviewer tự nguyện và runtime miễn phí được kiểm, đề xuất riêng
feasibility<=30phút, mộtGPU>=24GB, RAM>=16GB (headroom đề nghị, chưa đo), disk
tạm đủ stack/base. Kiểm allocation trước tải; chỉ synthetic có quyền được upload
vào notebook private sau Owner duyệt rõ đích. Không game/user/secret/Drive mount
toàn account hoặc public weights/corpus. Pin code/license dependency và kiểm
sharing/privacy/retention trước upload; private VM không là bảo đảm toàn dịch vụ.
Thiếu điều kiện giữ bước4 deferred, không đi săn provider/model khác.

Feasibility không tự là training authorization/semantic acceptance. Pilot sau
này phải freeze gold/split/criteria trước output, giữ OPUS/base Hy baseline,
no-new-major/protected tokens không nới; thiếu gold chỉ đo feasibility. Một lần
thử bounded trước; OOM/NaN/mất quota/thiếu20% memory headroom hoặc hết30phút
chưa forward-backward/save-reload thì dừng, không nâng cấp trả phí. Đây là stop
design, không một run đã được giao/thực hiện.

## Gói đề nghị để Brain trình Owner

“Cho DEV làm **offline M1–M4, tối đa5 giờ DEV/1 giờ Brain review, 0 đồng phát sinh**,
bằng evidence đã có; không dịch lại bằng model/thuê người/máy/upload/training.
Bàn giao silver, glossary/memory candidate và đóng research plan; training ghi
deferred.” Không bắt Owner thiết kế kỹ thuật hay duyệt hàng trăm câu.

Proposal đã được review rồi Owner giao M1–M4; phần offline đã bàn giao packet
ở đầu tài liệu. Brain read-only nghiệm thu data/technical, không human gold.
DEV sole implementation owner, Brain read-only nghiệm thu; không child/source
product/worker/validator change, download/install/account/payment/training/
inference/benchmark/release. **PASS phần chuẩn bị đề xuất**, không training hoặc
product acceptance. Thiếu human/compute chỉ hoãn bước4, không buộc thuê máy.
