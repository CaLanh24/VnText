# Hướng dẫn agent — VNText Studio

Áp dụng cho repository công khai và nhánh mặc định `main`; không phụ thuộc checkout, lịch sử riêng, dữ liệu game, cache hay artifact ngoài repository. `AI_STATE.md` là con trỏ trạng thái ngắn, không phải nhật ký. Khi Owner đưa ra quy tắc hoặc quyết định bền vững mới, ghi ngay vào tài liệu canonical trong cùng task; nếu chưa ghi được, báo rõ là chưa thành quy tắc bền vững.

## Quyền quyết định và điều phối

- Owner/PM-PO quyết định mục tiêu sản phẩm, ưu tiên, acceptance và hướng product/công nghệ. Lead xác định premise, owner kỹ thuật, contract, test và boundary; không tự thay product decision. Worker/Coder chỉ implement task đã bounded.
- Brain/reviewer/người điều phối chỉ gửi chỉ thị vào chat khác khi Owner đã ủy quyền. Trước mỗi lần gửi, đọc trực tiếp report/turn mới nhất của session đích, kiểm trạng thái task và đối chiếu evidence/Git liên quan; report Owner dán hoặc snapshot session cũ không thay bước này. Xác định việc đã khép, tồn đọng, blocker và quyền còn thiếu trước khi chọn tiếp tục task hay giao task mới. Ưu tiên khép tồn đọng; task mới/đổi ưu tiên cần yêu cầu Owner rõ ràng. Lời thảo luận, nghi vấn, than phiền hoặc ý tưởng chưa phải lệnh giao việc. Nếu chưa đọc được trạng thái mới nhất, chưa gửi chỉ thị. Không tạo writer thứ hai khi task hiện tại còn writer.
- Task implementation nêu ngắn mục tiêu, owner/phạm vi được sửa, quyền thực hiện, acceptance và điểm cần Owner quyết định. Coordinator tự tìm premise, contract và validation liên quan trước khi sửa; ghi rõ UNKNOWN khi chưa chứng minh. Prompt trỏ tới luật trong repo thay vì chép lại toàn bộ luật hoặc chỉ định từng lệnh.
- Mỗi task có đúng một Coordinator đang hoạt động, một lớp `Owner → Coordinator → Child` tối đa và một source writer tại một thời điểm. Coordinator có thể tự thực hiện task; chỉ route tuần tự cho một child khi có phần việc bounded cần bàn giao. Child không spawn child, không dùng parallel/council/loop và không tự mở task khác. Không mặc định tạo child theo độ nặng của lệnh hoặc khi onboarding.
- Tối đa **2 lần thử tạo child cho mỗi task**, tính cả lần tạo lỗi hoặc còn pending; retry không làm mới giới hạn. Child dùng tối đa **GPT-6 Luna Max** theo khả năng phiên; không nâng model hoặc mở thêm child chỉ vì task khó/thất bại.
- Lifecycle child: `route → terminal → Coordinator ingest/persist → archive`. Không archive khi child chưa terminal; ingest output/evidence, cập nhật tài liệu canonical nếu có rule mới, rồi mới đóng task. Khi Owner đã cho phép route child, Coordinator được gửi clarification/remediation trong cùng task, scope và giới hạn đã giao; thay mục tiêu, mở scope hoặc thêm quyền cần Owner quyết định.
- Theo việc tới acceptance đã giao: được tự đọc evidence, chẩn đoán, sửa lỗi do thay đổi của task hoặc lỗi ở prerequisite/gate bắt buộc trong owner đã bounded, rồi kiểm lại gate liên quan. Không xin lại quyền cho các bước này; thiếu môi trường không tự cấp quyền tải/cài hay chấp thuận license. Lỗi vượt owner/scope phải báo bằng chứng và đề xuất mở scope; tiếp tục phần độc lập còn làm được.
- Lỗi kỹ thuật đang có hướng xử lý trong scope là tiến độ, chưa phải terminal blocker. Kết thúc task bằng đúng một outcome: `PASS` khi acceptance đạt; `PROVEN_BLOCKED` khi thiếu quyền/prerequisite ngoài khả năng xử lý an toàn; `PREMISE_INVALID` khi evidence bác premise; `PM_DECISION_REQUIRED` khi cần quyết định sản phẩm. Blocked nêu điều kiện thiếu cụ thể, bằng chứng và phương án an toàn đã thử; không nới scope hay đổi verdict để tránh outcome.

## Bootstrap và bằng chứng

Khi vào repository lần đầu hoặc đổi repository, đọc `AGENTS.md` và `AI_STATE.md` để biết luật, trạng thái và con trỏ evidence; tra context spine theo nhu cầu dưới đây. Khi tiếp tục cùng task, chỉ đọc lại phần thay đổi hoặc phần cần cho bước tiếp theo, không đọc toàn bộ stack trước mỗi lệnh/edit.

- `ARCHITECTURE.md`: tìm owner, caller/dependency hoặc khi sửa seam/luồng chưa quen.
- `CONTRACTS.md`: invariant của vùng sẽ sửa; luôn đọc mục dữ liệu/artifact/Release liên quan trước thao tác tương ứng.
- `TEST_MATRIX.md`: chọn gate theo vùng thay đổi và acceptance; trước sửa source/test phải xác định gate liên quan.
- Source/test/log có mục tiêu là evidence chính. Với sửa câu chữ/docs đơn giản, đọc tài liệu sở hữu và references bị ảnh hưởng là đủ. Khi đổi scope hoặc có mâu thuẫn evidence, tra lại các mục liên quan. Dùng `rg`/`git grep`; không cần generated graph.

Chọn validation theo ladder focused → affected regression → integration/E2E → full/Release khi scope yêu cầu. Không lặp lại gate đã PASS nếu source và prerequisite liên quan không đổi, trừ acceptance bắt buộc. Docs-only dùng kiểm diff, references và gate docs có liên quan; không build/full regression chỉ vì sửa quy tắc. Báo command, exit code, fixture/artifact và mọi SKIP, warning hoặc blocker. Build, mock, file output hay log tự ghi PASS không tự chứng minh test, cài đặt hoặc release PASS. Evidence luôn giữ SHA thực đã chạy; sửa docs không tự nâng evidence cũ thành exact-HEAD Release PASS. Khi có lỗi, đọc output thật, sửa đúng nguyên nhân và chạy lại gate liên quan. Một giả thuyết remediation tối đa hai vòng nếu không có evidence mới; sau đó đổi sang thu evidence/kiểm premise, không lặp mù hoặc dừng chỉ vì hết hai vòng.

Bàn giao ngắn: đã đổi gì, đã kiểm gì trên SHA nào, acceptance còn thiếu và bước tiếp theo. Đánh giá hiệu quả theo task hoàn thành đúng acceptance, thời gian và usage/cost khi có số liệu; số test/token/child không tự là chất lượng. Chỉ đổi model/effort hoặc cơ chế điều phối khi Owner cho phép và có workload/evidence phù hợp; không suy khả năng từ tên model.

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

## Release và cập nhật

Phiên bản source lấy từ `VERSION.txt` cùng các version owner liên quan. Mỗi Setup/release cần evidence riêng từ đúng source, payload, hash và test của chính lần build đó; không suy ra phát hành từ tag dự kiến, metadata, mock hay artifact cục bộ.

Owner chọn dòng phiên bản public `0.1` (tag `v0.1`, source `0.1.0`); trạng thái giao bản và giới hạn kiểm chứng nằm trong `AI_STATE.md` và trang Release, không suy ra PASS từ tag. Offer/apply/restart stable GitHub 0.1.3 trên bản cài 0.1.2 đã PASS trong bounded scope; toàn product vẫn chưa `RELEASE_VERIFIED`. Người còn ở v0.1 dùng Setup 0.1.2; full-app update bắt đầu từ baseline mới theo `CONTRACTS.md` §10. Thay installer/uninstaller hoặc quyền hệ thống vẫn cần Setup mới. `Updates` cạnh Setup cục bộ không phải dịch vụ public update.

Không push, upload, tạo/xóa release hoặc thay đổi dịch vụ/dữ liệu ngoài repository nếu Owner chưa ủy quyền rõ cho task đó. Tuân thủ license, notices và provenance trong `THIRD_PARTY_NOTICES.md`; package metadata không tự chứng minh quyền phân phối.
