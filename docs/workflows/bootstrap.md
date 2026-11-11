<!-- Origin: docs/WORKFLOW.md at 242b5a97244234a4030a2ebf10bfa91ca72317cd; original section sha256 1876682301fc85cce6286ed1ab83b24ccb040bc406fabaaaea22bdd2897d70d4. Authority preserved, latest Owner instructions prevail. -->

## Bootstrap và bằng chứng

Khi vào repository lần đầu hoặc đổi repository, đọc `AGENTS.md` và `AI_STATE.md` để biết luật, trạng thái và con trỏ evidence; tra context spine theo nhu cầu dưới đây. Khi tiếp tục cùng task, chỉ đọc lại phần thay đổi hoặc phần cần cho bước tiếp theo, không đọc toàn bộ stack trước mỗi lệnh/edit.

- `ARCHITECTURE.md`: tìm owner, caller/dependency hoặc khi sửa seam/luồng chưa quen.
- `CONTRACTS.md`: invariant của vùng sẽ sửa; luôn đọc mục dữ liệu/artifact/Release liên quan trước thao tác tương ứng.
- `TEST_MATRIX.md`: chọn gate theo vùng thay đổi và acceptance; trước sửa source/test phải xác định gate liên quan.
- Source/test/log có mục tiêu là evidence chính. Với sửa câu chữ/docs đơn giản, đọc tài liệu sở hữu và references bị ảnh hưởng là đủ. Khi đổi scope hoặc có mâu thuẫn evidence, tra lại các mục liên quan. Dùng `rg`/`git grep`; không cần generated graph.

Chọn validation theo ladder focused → affected regression → integration/E2E → full/Release khi scope yêu cầu. Không lặp lại gate đã PASS nếu source và prerequisite liên quan không đổi, trừ acceptance bắt buộc. Docs-only dùng kiểm diff, references và gate docs có liên quan; không build/full regression chỉ vì sửa quy tắc. Báo command, exit code, fixture/artifact và mọi SKIP, warning hoặc blocker. Build, mock, file output hay log tự ghi PASS không tự chứng minh test, cài đặt hoặc release PASS. Evidence luôn giữ SHA thực đã chạy; sửa docs không tự nâng evidence cũ thành exact-HEAD Release PASS. Khi có lỗi, đọc output thật, sửa đúng nguyên nhân và chạy lại gate liên quan. Một giả thuyết remediation tối đa hai vòng nếu không có evidence mới; sau đó đổi sang thu evidence/kiểm premise, không lặp mù hoặc dừng chỉ vì hết hai vòng.

