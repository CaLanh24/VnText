# Vận hành agent và lưu trữ lịch sử

Quy tắc chi tiết được chuyển từ AGENTS.md tại commit `b7e842419bef`; [AGENTS.md](../AGENTS.md) là điểm vào bắt buộc. Chỉ đọc mục cần dùng. Chỉ thị Owner mới nhất ưu tiên hơn snapshot/quy tắc cũ được nạp lại; snapshot không phải một quyết định mới. Không tự thay model/effort.

## Luồng tiếp tục tối thiểu

1. Đọc AGENTS và AI_STATE; xác nhận quyền/mục tiêu, writer, Git và đúng candidate.
2. Tìm chủ đề trong INDEX; chỉ đọc contract/gate cần cho thao tác kế tiếp.
3. Đọc delta DEV/receipt từ cursor; không đọc lại transcript hay toàn bộ ledger.
4. Khép một acceptance cụ thể, cập nhật checkpoint/receipt nhỏ; giữ verdict và SHA thật.

## Phân lớp trạng thái và lịch sử

| Lớp | Nơi lưu | Cách đọc/cập nhật |
|---|---|---|
| Quy tắc vận hành | AGENTS và tài liệu này | Thay rule cũ khi Owner đổi; không nhân bản vào từng report |
| Invariant/gate | CONTRACTS, TEST_MATRIX theo mục | Source/tests kiểm chứng; quyết định Owner xác định authority |
| Trạng thái đang làm | AI_STATE | Một bản hiện hành, không nối nhiều đoạn “supersedes below” |
| Acceptance task hiện tại | Ledger được AI_STATE trỏ tới | Checklist hiện tại, receipt pointer, phạm vi và phần còn thiếu |
| Lịch sử task/chủ đề | docs/history và ledger có ngày | Tra từ INDEX theo câu hỏi/ID; không tự tiếp tục quyền/task cũ |
| Raw/tool events | Log/receipt ngoài Git và cursor DEV | Đọc đoạn/trường cần thiết; cleanup bulk theo lifecycle |

AI_STATE hướng tới 1.500 từ/12 KiB; gói phục hồi thông thường gồm AGENTS + AI_STATE + các đoạn liên quan, không đọc toàn INDEX/ledger/history. Ledger hiện tại hướng tới 16 KiB; nếu vượt vì chronology, chuyển phần đã khép sang history một lần, giữ checklist/contract còn hiệu lực và liên kết. Đây là mục tiêu tổ chức, không là guard quota mới và không được cắt bỏ authority hoặc evidence thiết yếu.

Khi chuyển lịch sử: giữ nguyên bytes/SHA/verdict, ghi origin và commit trong INDEX; không sửa archive để nó trông như kết quả hiện tại. Đường dẫn tương đối trong archive được hiểu theo origin của snapshot (INDEX ghi rõ). Liên kết được dùng để điều hướng phải resolve tới vị trí thật; anchor cũ ở landing page chỉ là compatibility pointer tới archive. Không replay archive để bootstrap. Không dùng số dòng làm giới hạn output: bảng dài/JSON phải chọn field/range.

Checkpoint sau compaction cần goal/authority/exclusions, sole writer/DEV ID/cursor, candidate/source, acceptance đã đạt/còn thiếu, receipt và một bước kế tiếp. Tự compact khi runtime hỗ trợ và cần thiết; không có ngưỡng %/số phase tạo session mới. Chỉ bàn giao tuần tự khi Owner yêu cầu hoặc phục hồi đã thất bại có bằng chứng. Không giả vờ có công cụ compact; thiếu công cụ thủ công không tự buộc đổi Brain.

Không commit checkpoint sau mỗi tool call. Khi epoch đang active, ghi delta tạm trong receipt ignored được AI_STATE trỏ rõ; gom cập nhật tracked ở boundary docs/source có sẵn trước activation tiếp theo. Không tạo vòng docs → epoch → docs. Không chạy lại gate hợp lệ chỉ vì tổ chức tài liệu.

## Quy tắc chi tiết được giữ nguyên

## Quyền quyết định và điều phối

- Owner/PM-PO quyết định mục tiêu sản phẩm, ưu tiên, acceptance và hướng product/công nghệ. Lead xác định premise, owner kỹ thuật, contract, test và boundary; không tự thay product decision. Worker/Coder chỉ implement task đã bounded.
- Brain/reviewer/người điều phối chỉ gửi chỉ thị vào chat khác khi Owner đã ủy quyền. Trước mỗi lần gửi, đọc trực tiếp report/turn mới nhất của session đích, kiểm trạng thái task và đối chiếu evidence/Git liên quan; report Owner dán hoặc snapshot session cũ không thay bước này. Xác định việc đã khép, tồn đọng, blocker và quyền còn thiếu trước khi chọn tiếp tục task hay giao task mới. Ưu tiên khép tồn đọng; task mới/đổi ưu tiên cần yêu cầu Owner rõ ràng. Lời thảo luận, nghi vấn, than phiền hoặc ý tưởng chưa phải lệnh giao việc. Nếu chưa đọc được trạng thái mới nhất, chưa gửi chỉ thị. Không tạo writer thứ hai khi task hiện tại còn writer.
- Task implementation nêu ngắn mục tiêu, owner/phạm vi được sửa, quyền thực hiện, acceptance và điểm cần Owner quyết định. Coordinator tự tìm premise, contract và validation liên quan trước khi sửa; ghi rõ UNKNOWN khi chưa chứng minh. Prompt trỏ tới luật trong repo thay vì chép lại toàn bộ luật hoặc chỉ định từng lệnh.
- Mỗi task có đúng một Coordinator đang hoạt động, một lớp `Owner → Coordinator → Child` tối đa và một source writer tại một thời điểm. Coordinator có thể tự thực hiện task; chỉ route tuần tự cho một child khi có phần việc bounded cần bàn giao. Child không spawn child, không dùng parallel/council/loop và không tự mở task khác. Không mặc định tạo child theo độ nặng của lệnh hoặc khi onboarding.
- Tối đa **2 lần thử tạo child cho mỗi task**, tính cả lần tạo lỗi hoặc còn pending; retry không làm mới giới hạn. Child dùng tối đa **GPT-6 Luna Max** theo khả năng phiên; không nâng model hoặc mở thêm child chỉ vì task khó/thất bại.
- Lifecycle child: `route → terminal → Coordinator ingest/persist → archive`. Không archive khi child chưa terminal; ingest output/evidence, cập nhật tài liệu canonical nếu có rule mới, rồi mới đóng task. Khi Owner đã cho phép route child, Coordinator được gửi clarification/remediation trong cùng task, scope và giới hạn đã giao; thay mục tiêu, mở scope hoặc thêm quyền cần Owner quyết định.
- Quyết định điều phối riêng của workflow hiện tại trong `CONTRACTS.md` (Owner coordination decision for the current 0.1.13 workflow) được ưu tiên hơn các quy tắc child/route ở trên khi mâu thuẫn, chỉ trong workflow đó; các quy tắc chung không bị bãi bỏ.
- Theo việc tới acceptance đã giao: được tự đọc evidence, chẩn đoán, sửa lỗi do thay đổi của task hoặc lỗi ở prerequisite/gate bắt buộc trong owner đã bounded, rồi kiểm lại gate liên quan. Không xin lại quyền cho các bước này; thiếu môi trường không tự cấp quyền tải/cài hay chấp thuận license. Lỗi vượt owner/scope phải báo bằng chứng và đề xuất mở scope; tiếp tục phần độc lập còn làm được.
- Lỗi kỹ thuật đang có hướng xử lý trong scope là tiến độ, chưa phải terminal blocker. Kết thúc task bằng đúng một outcome: `PASS` khi acceptance đạt; `PROVEN_BLOCKED` khi thiếu quyền/prerequisite ngoài khả năng xử lý an toàn; `PREMISE_INVALID` khi evidence bác premise; `PM_DECISION_REQUIRED` khi cần quyết định sản phẩm. Blocked nêu điều kiện thiếu cụ thể, bằng chứng và phương án an toàn đã thử; không nới scope hay đổi verdict để tránh outcome.

## Bootstrap và bằng chứng

Khi vào repository lần đầu hoặc đổi repository, đọc `AGENTS.md` và `AI_STATE.md` để biết luật, trạng thái và con trỏ evidence; tra context spine theo nhu cầu dưới đây. Khi tiếp tục cùng task, chỉ đọc lại phần thay đổi hoặc phần cần cho bước tiếp theo, không đọc toàn bộ stack trước mỗi lệnh/edit.

- `ARCHITECTURE.md`: tìm owner, caller/dependency hoặc khi sửa seam/luồng chưa quen.
- `CONTRACTS.md`: invariant của vùng sẽ sửa; luôn đọc mục dữ liệu/artifact/Release liên quan trước thao tác tương ứng.
- `TEST_MATRIX.md`: chọn gate theo vùng thay đổi và acceptance; trước sửa source/test phải xác định gate liên quan.
- Source/test/log có mục tiêu là evidence chính. Với sửa câu chữ/docs đơn giản, đọc tài liệu sở hữu và references bị ảnh hưởng là đủ. Khi đổi scope hoặc có mâu thuẫn evidence, tra lại các mục liên quan. Dùng `rg`/`git grep`; không cần generated graph.

Chọn validation theo ladder focused → affected regression → integration/E2E → full/Release khi scope yêu cầu. Không lặp lại gate đã PASS nếu source và prerequisite liên quan không đổi, trừ acceptance bắt buộc. Docs-only dùng kiểm diff, references và gate docs có liên quan; không build/full regression chỉ vì sửa quy tắc. Báo command, exit code, fixture/artifact và mọi SKIP, warning hoặc blocker. Build, mock, file output hay log tự ghi PASS không tự chứng minh test, cài đặt hoặc release PASS. Evidence luôn giữ SHA thực đã chạy; sửa docs không tự nâng evidence cũ thành exact-HEAD Release PASS. Khi có lỗi, đọc output thật, sửa đúng nguyên nhân và chạy lại gate liên quan. Một giả thuyết remediation tối đa hai vòng nếu không có evidence mới; sau đó đổi sang thu evidence/kiểm premise, không lặp mù hoặc dừng chỉ vì hết hai vòng.

## Ngữ cảnh và phục hồi Coordinator

Owner (2026-10-27, CONTEXT-HISTORY-POLICY) bác bỏ việc tự động mở Brain/session mới ở 40/50% context hay sau hai phase; quy tắc đó thay các điều khoản cũ ngay. Model/effort do Owner chọn, PM không override. Giữ một Coordinator và cùng một Claude DEV; phần dưới là vận hành phiên hiện tại, phục hồi và truy xuất lịch sử.

- `AI_STATE.md` là checkpoint hiện hành, cỡ khoảng 1.500 từ (~12 KiB UTF-8; không chỉ giới hạn số dòng): trạng thái/thời điểm, quyền và loại trừ của Owner, writer/DEV ID/cursor, source/candidate, acceptance đã đạt và còn MỞ, bước tiếp theo, blocker và liên kết receipt. Thay thông tin cũ thay vì nối nhật ký; không cắt sự kiện an toàn/quyền cần thiết để đạt con số. Mọi checkpoint nạp vào là tham khảo cho đến khi đối chiếu Git/evidence. Không commit checkpoint sau mỗi tool call: trong giao dịch source/epoch giữ kết quả sống ở receipt/checkpoint DEV_RUN bị ignore, và con trỏ tracked chỉ cập nhật ở commit docs/source hiện có kế tiếp, trước khi kích hoạt epoch tiếp theo.
- Trước mỗi phase, chốt danh sách acceptance hữu hạn và gate liên quan. Không mở scope mới. Chỉ chạy lại gate đã PASS khi source/prerequisite ảnh hưởng thay đổi hoặc acceptance thực sự yêu cầu; ghi lý do và các gate bị mất hiệu lực trước rebuild. Sau 30 phút không khép được mục nào, persist nguyên nhân và đổi cách chẩn đoán thay vì tiếp tục lặp.
- Đọc log/diff/receipt có mục tiêu; mặc định tối đa khoảng 2.000 token mỗi kết quả và 20 event DEV, mở rộng từng phần khi có câu hỏi cụ thể. Lưu log đầy đủ ra file; không nạp lại toàn transcript/JSON/UI tree hoặc lặp snapshot không đổi. Wait dùng cursor tiến dần và khoảng chờ phù hợp; kết quả không đổi không phải tiến độ mới.
- Context % là tín hiệu áp lực, không phải điều kiện thay thế. Tại ranh giới phase mạch lạc, hoặc trước compaction được runtime thật sự hỗ trợ (thủ công/tự động) khi có thể, persist checkpoint nhỏ. Không bịa công cụ compact, không khẳng định đã reset/compact khi không có bằng chứng, không poll số token liên tục. Sau compaction/resume: đọc thay đổi AGENTS liên quan, checkpoint AI_STATE, `git status` và chỉ các sự kiện DEV/receipt mới từ cursor đã lưu; xác nhận mục tiêu, quyền, candidate và bước tiếp theo; không replay transcript hay chạy lại gate đã hợp lệ. Thiếu công cụ compact thủ công không tự là lý do thay session.
- Chỉ thay Brain khi quan sát được phục hồi thất bại (lặp lại mất quyết định/bước tiếp theo hiện hành sau khi đã dùng checkpoint, hoặc giới hạn lịch sử/công cụ khiến không làm việc hữu ích được) hoặc theo yêu cầu của Owner; trước đó thử phục hồi bằng checkpoint và giảm output công cụ quá lớn. Thay thế là tuần tự, context sạch, cùng sole DEV; Brain cũ dừng giao việc và bàn giao ID/cursor/quyền/candidate/trạng thái DEV, Brain mới xác minh checkpoint với Git/receipt. Không có ngưỡng phần trăm, số lần compaction hay số phase nào tự động mở Brain mới. Codex chỉ tạm thay DEV khi Claude thật sự hết quota và trả lại ngay khi hồi phục theo CONTRACTS. Compaction không đổi quyền, validator hay tiêu chí acceptance.
- Lịch sử: dùng lại ledger của task; đặt một current summary ngắn ở đầu (task ID, trạng thái hiện hành/đã đóng/bị thay thế, quyết định có thẩm quyền, phạm vi và khoảng trống acceptance, receipt mới nhất, bước tiếp theo), các phần theo thời gian bên dưới là HISTORY; không viết lại SHA/verdict/receipt cũ hay biến PARTIAL cũ thành PASS. Chỉ ghi delta có nghĩa của phase (quyết định/thay đổi, source chính xác, verdict + con trỏ receipt, evidence bị vô hiệu, vấn đề còn mở, bước tiếp theo), không ghi mọi lệnh/chờ/UI tree. Truy xuất theo câu hỏi/ID: tìm heading/index rồi đọc một phần hoặc trường receipt có giới hạn, gói phục hồi mặc định khoảng ≤ 3.000 từ; bảng/JSON/dòng dài đọc theo field/range. Quyết định bền mới chỉ viết một lần vào canonical sở hữu rồi liên kết. Quota stop, context usage và chất lượng điều phối là ba trạng thái riêng.

## Computer Use lifecycle

- Chỉ khởi tạo Computer Use ngay trước khi cần thao tác native UI thật. Khi tác vụ native kết thúc, chuyển sang kiểm tra backend, chờ, bị dừng/interrupt/usage limit, hoặc gặp lỗi, phải hủy thao tác input/capture còn pending và dispose/reset session/kernel Computer Use do task sở hữu bằng API được hỗ trợ. Đóng app không đồng nghĩa đã đóng Computer Use.
- Không để input/capture/automation loop chạy nền khi task idle, terminal hoặc đã chuyển sang phương thức khác. Khi resume sau interrupt, crash hoặc usage limit, kiểm tra session/tác vụ Computer Use mồ côi trước khi khởi tạo session mới.
- Phân biệt session/kernel của task với process tool server dùng chung. Chỉ dispose/reset resource có quyền sở hữu rõ ràng; không kill process Node/Codex dùng chung để dọn một session chưa xác định.
- Báo trạng thái dispose/reset, thao tác còn pending và process app/worker do task sở hữu trong biên bản terminal. Nếu không xác minh được ownership hoặc trạng thái, ghi `UNKNOWN` và nêu giới hạn thay vì tự kết thúc process dùng chung.

Bàn giao ngắn: đã đổi gì, đã kiểm gì trên SHA nào, acceptance còn thiếu và bước tiếp theo. Đánh giá hiệu quả theo task hoàn thành đúng acceptance, thời gian và usage/cost khi có số liệu; số test/token/child không tự là chất lượng. Chỉ đổi model/effort hoặc cơ chế điều phối khi Owner cho phép và có workload/evidence phù hợp; không suy khả năng từ tên model.

## Quy tắc workspace và đường dẫn

- Dùng checkout/candidate root nông và tên scope/run ngắn, duy nhất; tránh clone lồng nhiều tầng, scope path lặp sâu và các thư mục `tmp` lồng nhau chỉ để né giới hạn đường dẫn hoặc quota.
- Trước validation hoặc allocation, kiểm độ sâu và đường dẫn tuyệt đối dài nhất cùng số entry/độ dài `PATH` ở Process/User/Machine. Không thêm các thư mục tạm lặp lại vào `PATH`; dùng `TEMP`/`TMP` ngắn, ổn định bên trong scope đã đăng ký cho lượt chạy và khôi phục sau đó. Không tự đổi biến môi trường User/Machine.
- Giữ repository portable: đường dẫn local do Owner chọn chỉ ghi trong `AI_STATE.md`/receipt phù hợp, không trở thành yêu cầu hardcode cho public clone.

Trước DEV validation hoặc game E2E, chốt scope, gate order, run/copy budget, executable provenance, prerequisite và cleanup theo `CONTRACTS.md` §10c; dùng `TEST_MATRIX.md` để chọn gate. Persist evidence từng bước trước bước phụ thuộc; outcome test và cleanup riêng.

## Invariants sản phẩm

- Workflow: extract → translate/import CSV → patch. Giữ key, schema/thứ tự CSV, manifest, locator, placeholder, tag, biến, newline, escape và engine boundary.
- Unity là engine đầu tiên, không có nghĩa hỗ trợ mọi game Unity. Chỉ quảng bá capability khi có extract, provenance, patch/write-back và verification tương ứng.
- Route dịch sản phẩm hiện là CTranslate2/OPUS-MT. Không khôi phục Argos hoặc VinAI nếu Owner chưa quyết định lại; Hy-MT2 chỉ test-only.
- Không đổi worker protocol, semantic workflow, game behavior, model, framework hay architecture nếu task không yêu cầu. Không hạ validator hoặc biến dữ liệu lỗi thành hợp lệ giả.
- Patch phải qua preflight/gate, backup và verification. Không thử trên game gốc hoặc dữ liệu user; test game chỉ dùng fixture/bản copy được khai báo.

## Git, dữ liệu và artifacts

Trước lần sửa đầu tiên của task, xác nhận đang ở `main`, checkout sạch và không có writer khác. Nếu không đạt, dừng mutation và báo; không stash/reset/checkout để né trạng thái. Trong task, giữ thay đổi của chính task và kiểm status/diff trước commit; thay đổi lạ hoặc HEAD đổi phải đối chiếu trước khi ghi tiếp. Task docs riêng vẫn phải giữ một source writer; agent đang chạy test/app trên snapshot không tự chứng minh là source writer. Chỉ stage và commit source/test/docs đúng task scope sau validation khi task không chỉ định khác; xem lại status, staged/unstaged diff, `git diff --check` và log trước commit. Không push, merge, force-push, sửa config Git, bỏ hook hoặc rewrite history nếu Owner không yêu cầu rõ.

Khi sửa WPF hoặc runtime app, để lại tối đa một executable thử được trong `DEV_RUN` và chạy `--smoke-worker`; docs/test-only không cần build executable. Dependency Python/SDK/model/cache dùng chung nằm trong `.dev-env/.venv` và các thư mục con `.dev-env`; test runtime chỉ nằm trong `TEST_RUN` và phải tự dọn absent/empty khi terminal; Release task mới được tạo `RELEASE_RUN`. Không bắt đầu task mới khi transient root cũ chưa terminal hoặc còn UNKNOWN. Chi tiết lifecycle, OWNER_TEST_PENDING và giới hạn evidence nằm ở `CONTRACTS.md` §10a.

Chỉ sửa file trong scope; giữ nguyên thay đổi ngoài scope. Không xóa/di chuyển/ghi đè game, save, CSV/glossary user, output hoặc môi trường phát triển nếu chưa được phép. Không commit game, model, release binary, log lớn, cache hay secret. Cleanup/evidence tuân theo `CONTRACTS.md` và gate của `TEST_MATRIX.md`; private historical artifacts không là prerequisite của public clone và việc thiếu chúng không chứng minh PASS hay FAIL hiện tại.

## Cleanup và retention

- Mỗi allocation/artifact có owner, task, đường dẫn tuyệt đối, kích thước, consumer đang dùng, điều kiện hết hạn và bước dọn. RETAINED/UNKNOWN/“để làm evidence” không tự tạo quyền giữ vô hạn: retention cần consumer cụ thể và mốc rà lại; UNKNOWN phải được điều tra (owner/Git/process/consumer) ở checkpoint cleanup kế tiếp, câu hỏi chưa giải quyết ghi kèm owner xử lý và mốc rà lại.
- Sau mỗi phase và trước allocation lớn, dọn scratch/output/build copy hết consumer; cuối task dọn mọi disposable. Một release đang mở không giữ hộ artifact của task/release cũ; không chờ publication để dọn bản stale. Chỉ giữ candidate hiện hành, baseline/fixture có consumer acceptance hoặc route rõ, repro gắn finding còn mở, và shared env/model/SDK đang cần.
- Evidence mặc định là receipt gọn (SHA, lệnh/exit, verdict, hash/count/bytes, finding, đoạn log cần thiết; mục tiêu ≤ 20 MiB/task, vượt phải có lý do và mốc rà lại). Không giữ installer, cây giải nén, output/build hàng loạt hay cache trùng chỉ để làm bằng chứng; ghi rõ payload đã disposed, không hứa chạy lại artifact đã xóa.
- Cleanup chạy theo plan có đường dẫn tuyệt đối, bytes, bằng chứng ownership/hết consumer và exclusions, tại ranh giới an toàn (không song song với writer/test/native, không cắt giao dịch epoch), qua helper/registry đúng lifecycle; không follow link ra ngoài root, không kill process dùng chung, không xóa source bẩn/user data, không đụng epoch đang hoạt động. Báo before/after, đường dẫn đã dọn, phần còn giữ + consumer + hạn, và cleanup verdict riêng; chỉ tuyên bố đã dọn sau readback. Chi tiết: `CONTRACTS.md` §10a.

## Release và cập nhật

Phiên bản source lấy từ `VERSION.txt` cùng các version owner liên quan. Mỗi Setup/release cần evidence riêng từ đúng source, payload, hash và test của chính lần build đó; không suy ra phát hành từ tag dự kiến, metadata, mock hay artifact cục bộ.

Owner chọn dòng phiên bản public `0.1` (tag `v0.1`, source `0.1.0`); trạng thái giao bản và giới hạn kiểm chứng nằm trong `AI_STATE.md` và trang Release, không suy ra PASS từ tag. Offer/apply/restart stable GitHub 0.1.3 trên bản cài 0.1.2 đã PASS trong bounded scope; toàn product vẫn chưa `RELEASE_VERIFIED`. Người còn ở v0.1 dùng Setup 0.1.2; full-app update bắt đầu từ baseline mới theo `CONTRACTS.md` §10. Thay installer/uninstaller hoặc quyền hệ thống vẫn cần Setup mới. `Updates` cạnh Setup cục bộ không phải dịch vụ public update.

Không push, upload, tạo/xóa release hoặc thay đổi dịch vụ/dữ liệu ngoài repository nếu Owner chưa ủy quyền rõ cho task đó. Tuân thủ license, notices và provenance trong `THIRD_PARTY_NOTICES.md`; package metadata không tự chứng minh quyền phân phối.
