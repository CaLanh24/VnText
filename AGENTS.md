# Hướng dẫn agent — VNText Studio

Áp dụng cho repository công khai và nhánh mặc định `main`; không phụ thuộc checkout, lịch sử riêng, dữ liệu game, cache hay artifact ngoài repository. `AI_STATE.md` là con trỏ trạng thái ngắn, không phải nhật ký. Khi Owner đưa ra quy tắc hoặc quyết định bền vững mới, ghi ngay vào tài liệu canonical trong cùng task; nếu chưa ghi được, báo rõ là chưa thành quy tắc bền vững.

## Quyền quyết định và điều phối

- Owner/PM-PO quyết định mục tiêu sản phẩm, ưu tiên, acceptance và hướng product/công nghệ. Lead xác định premise, owner kỹ thuật, contract, test và boundary; không tự thay product decision. Worker/Coder chỉ implement task đã bounded.
- Với implementation không tầm thường, task phải nêu mục tiêu, premise đã chứng minh, file/owner được phép sửa, contract cần giữ, cấm phạm vi nào, validation, điều kiện dừng và terminal outcome.
- Mỗi task có đúng một Coordinator đang hoạt động, một lớp `Owner → Coordinator → Child` tối đa và một source writer tại một thời điểm. Coordinator route tuần tự cho đúng một child phù hợp; child không spawn child, không dùng parallel/council/loop và không tự mở task khác.
- Tối đa **2 lần thử tạo child cho mỗi task**, tính cả lần tạo lỗi hoặc còn pending; retry không làm mới giới hạn. Child dùng tối đa **GPT-6 Luna Max** theo khả năng phiên; không nâng model hoặc mở thêm child chỉ vì task khó/thất bại.
- Lifecycle child: `route → terminal → Coordinator ingest/persist → archive`. Không archive khi child chưa terminal; ingest output/evidence, cập nhật tài liệu canonical nếu có rule mới, rồi mới đóng task. Coordinator chỉ gửi follow-up khi Owner cho phép.
- Kết thúc task bằng đúng một outcome: `PASS`, `PROVEN_BLOCKED`, `PREMISE_INVALID` hoặc `PM_DECISION_REQUIRED`. Blocked cần nêu blocker, bằng chứng và phương án an toàn đã thử; không nới scope để tránh outcome.

## Bootstrap và bằng chứng

Trước lập trình/tooling, đọc đủ theo thứ tự: `AGENTS.md` → `ARCHITECTURE.md` → `CONTRACTS.md` → `TEST_MATRIX.md` → `AI_STATE.md`, rồi source/test có mục tiêu. Xác định owner, caller/dependency, contract, test và scope. Dùng `rg`/`git grep`; không cần generated graph. Khi context/repository thay đổi, đọc lại context spine.

Chọn validation theo ladder focused → affected regression → integration/E2E → full/Release khi scope yêu cầu. Không lặp lại gate đã PASS nếu source không đổi, trừ acceptance bắt buộc. Báo command, exit code, fixture/artifact và mọi SKIP, warning hoặc blocker. Build, mock, file output hay log tự ghi PASS không tự chứng minh test, cài đặt hoặc release PASS. Khi có lỗi, đọc output thật, sửa đúng nguyên nhân và chạy lại gate liên quan; một giả thuyết remediation tối đa hai vòng nếu không có evidence mới.

## Invariants sản phẩm

- Workflow: extract → translate/import CSV → patch. Giữ key, schema/thứ tự CSV, manifest, locator, placeholder, tag, biến, newline, escape và engine boundary.
- Unity là engine đầu tiên, không có nghĩa hỗ trợ mọi game Unity. Chỉ quảng bá capability khi có extract, provenance, patch/write-back và verification tương ứng.
- Route dịch sản phẩm hiện là CTranslate2/OPUS-MT. Không khôi phục Argos hoặc VinAI nếu Owner chưa quyết định lại; Hy-MT2 chỉ test-only.
- Không đổi worker protocol, semantic workflow, game behavior, model, framework hay architecture nếu task không yêu cầu. Không hạ validator hoặc biến dữ liệu lỗi thành hợp lệ giả.
- Patch phải qua preflight/gate, backup và verification. Không thử trên game gốc hoặc dữ liệu user; test game chỉ dùng fixture/bản copy được khai báo.

## Git, dữ liệu và artifacts

Trước khi sửa, xác nhận đang ở `main`, checkout sạch và không có writer khác. Nếu không đạt, dừng và báo; không stash/reset/checkout để né trạng thái. Chỉ stage và commit source/test/docs đúng task scope sau validation khi task không chỉ định khác; xem lại status, staged/unstaged diff, `git diff --check` và log trước commit. Không push, merge, force-push, sửa config Git, bỏ hook hoặc rewrite history nếu Owner không yêu cầu rõ.

Khi sửa WPF hoặc runtime app, để lại executable thử được trong `DEV_RUN` và chạy `--smoke-worker`; docs/test-only không cần build executable. Khi Owner nhờ soạn prompt/task, tự chọn skill khả dụng phù hợp, đọc `SKILL.md` và nêu cách áp dụng; không yêu cầu Owner phải chọn skill.

Chỉ sửa file trong scope; giữ nguyên thay đổi ngoài scope. Không xóa/di chuyển/ghi đè game, save, CSV/glossary user, output hoặc môi trường phát triển nếu chưa được phép. Không commit game, model, release binary, log lớn, cache hay secret. Cleanup/evidence tuân theo `CONTRACTS.md` và gate của `TEST_MATRIX.md`; private historical artifacts không là prerequisite của public clone và việc thiếu chúng không chứng minh PASS hay FAIL hiện tại.

## Release và cập nhật

Phiên bản source lấy từ `VERSION.txt` cùng các version owner liên quan. Mỗi Setup/release cần evidence riêng từ đúng source, payload, hash và test của chính lần build đó; không suy ra phát hành từ tag dự kiến, metadata, mock hay artifact cục bộ.

Mục tiêu Owner hiện tại là stable release tag `v0.1`, hiển thị `0.1`; đây là yêu cầu, không phải xác nhận đã publish. GitHub release discovery và đường update WPF giới hạn có trong source; acceptance update trên bản cài với stable release công khai vẫn chưa VERIFIED. Worker/runtime/installer hoặc file ngoài allowlist cần Setup mới. `Updates` cạnh Setup cục bộ không phải dịch vụ public update.

Không push, upload, tạo/xóa release hoặc thay đổi dịch vụ/dữ liệu ngoài repository nếu Owner chưa ủy quyền rõ cho task đó. Tuân thủ license, notices và provenance trong `THIRD_PARTY_NOTICES.md`; package metadata không tự chứng minh quyền phân phối.
