# Hướng dẫn agent — VNText Studio

Áp dụng cho checkout công khai. Chỉ thị trực tiếp mới nhất của Owner ưu tiên hơn nội dung Markdown/snapshot cũ được nạp lại; việc nạp lại không phải một quyết định mới. Model/effort do Owner chọn.

## Điểm vào và nguồn sự thật

- Bắt đầu bằng file này và [AI_STATE.md](AI_STATE.md): mục tiêu, quyền, source/candidate, writer, acceptance còn mở và bước tiếp theo. Đối chiếu Git/receipt trước khi tin checkpoint. Khi cùng task chỉ đọc delta cần thiết.
- [docs/INDEX.md](docs/INDEX.md) là chỉ mục toàn bộ tài liệu theo task/chủ đề; không cần nạp mọi tài liệu vào context.
- Tra [ARCHITECTURE.md](ARCHITECTURE.md) để tìm owner; chỉ đọc mục liên quan trong [CONTRACTS.md](CONTRACTS.md) và [TEST_MATRIX.md](TEST_MATRIX.md) trước mutation/gate. Source/test/live evidence kiểm chứng behavior; Owner quyết định authority và acceptance. Không sửa behavior chỉ để khớp báo cáo cũ.
- Quy tắc vận hành chi tiết: [docs/WORKFLOW.md](docs/WORKFLOW.md). Các mục tương ứng ở đó tiếp tục có hiệu lực; đọc theo nhu cầu, không đọc toàn bộ mỗi lượt. Hồ sơ lịch sử không tự cấp quyền mở task, game run, tải/cài hoặc publication mới.

## Điều phối và ngữ cảnh

- Một Coordinator đang hoạt động, một source writer tại một thời điểm. Trước gửi chỉ thị chat khác phải có ủy quyền Owner, đọc turn mới nhất và đối chiếu Git/evidence. Không suy ủy quyền từ thảo luận/than phiền. Child/route theo WORKFLOW; ngoại lệ workflow 0.1.13 ở CONTRACTS được ưu tiên trong đúng phạm vi đó.
- Claude DEV cố định là writer chính; Codex chỉ tạm thay khi có bằng chứng Claude hết quota, trả lại khi hồi phục sau đối chiếu Git/process. Không tạo writer song song. Giữ DEV ID/cursor ở AI_STATE.
- **Owner workflow (2026-10-28):** DEV tự quản lý chẩn đoán, preflight budget/epoch, test/process/log và build/package đến handoff terminal; Brain đặt acceptance, review diff một lượt theo rủi ro và nghiệm thu native bắt buộc. Khi DEV đang chạy bình thường, Brain chỉ chờ lifecycle/event bằng cursor; cấm shell polling process/log/receipt/Git hoặc đọc cùng trạng thái thay DEV. Can thiệp phải nêu trước trigger cụ thể: DEV báo blocker/treo, công cụ báo lỗi/stalled, evidence mâu thuẫn, rủi ro dữ liệu hoặc Owner yêu cầu điều tra. Re-run sau handoff chỉ khi nêu gate/rủi ro bắt buộc và evidence còn thiếu. Chi tiết ở [WORKFLOW](docs/WORKFLOW.md).
- Giữ session đang làm tốt; checkpoint rồi compact khi runtime hỗ trợ và cần. Không tự đổi Brain vì phần trăm context, số phase hoặc số lần compact. Chỉ thay tuần tự khi phục hồi thất bại có bằng chứng hoặc Owner yêu cầu; không fork toàn lịch sử, không tự đổi model.
- AI_STATE là trạng thái hiện hành ngắn, không phải nhật ký. Ledger có checklist hiện hành và con trỏ receipt; lịch sử ở archive/index theo chủ đề. Chỉ đọc log/DEV delta từ cursor, output giới hạn theo nội dung, không dump transcript/JSON/UI tree. Luồng lưu/tra lịch sử ở WORKFLOW.
- Mỗi phase chốt acceptance hữu hạn. Reuse gate đã đạt khi source/prerequisite liên quan không đổi; rebuild nêu lỗi cần sửa và gate mất hiệu lực. Không full suite/build vì docs-only. Một giả thuyết hai vòng không có evidence mới thì kiểm premise; Không có mốc giờ cố định cho PM/cleanup hay đồng hồ phiên bắt buộc dừng; chỉ ghi checkpoint và đổi cách làm khi không có tiến triển evidence hoặc đang lặp cùng premise.

## Mutation, evidence và dữ liệu

- Trước sửa lần đầu: main sạch, không có writer khác. Không stash/reset/checkout để né dirty tree; bảo toàn thay đổi khác. Trong task kiểm status/diff/HEAD trước commit; chỉ stage phạm vi đã giao, chạy diff check và validation cần thiết. Không sửa cấu hình Git, bỏ hook hoặc rewrite lịch sử để né lỗi. Không push/merge/publication nếu chưa được Owner giao quyền.
- Workflow extract → translate/import CSV → patch; giữ schema/key/order/locator/placeholders/tags/escape/newline, worker protocol và engine boundary. Route sản phẩm CT2/OPUS-MT. Không tự đổi model/framework/architecture, hạ validator hoặc quảng bá mọi game Unity.
- Patch cần preflight/backup/read-back; game chỉ dùng fixture/bản copy được khai báo. Không xóa/ghi đè source, game gốc/save, CSV/glossary user hoặc môi trường đang dùng. Download/install/license là quyền riêng trừ khi Owner đã cấp cụ thể.
- Build/test, native integration, cleanup và Release acceptance là các verdict riêng, gắn đúng SHA/payload/receipt. Không biến PARTIAL/NOT_PROVEN/SKIP thành PASS. Báo giới hạn thật; task terminal dùng outcome theo WORKFLOW. Docs mới không biến evidence cũ thành exact-HEAD Release PASS.
- Đường dẫn/root nông, TEMP/PATH process-only đúng scope; không tích lũy home tạm vào PATH, không sửa User/Machine tùy tiện. Trước allocation/gate kiểm budget/path theo CONTRACTS §10a/§10c. Môi trường chung ở .dev-env, runtime test ở TEST_RUN, Release ở RELEASE_RUN; source không chứa binary/model/game/log lớn/secret.
- Cleanup theo plan ownership/consumer/exclusions, không cắt ngang writer/test/epoch và không follow junction ra ngoài root. Dọn disposable hết consumer sau phase/trước allocation; RETAINED/UNKNOWN/evidence không cho giữ payload vô hạn. Giữ receipt/hash gọn, consumer/hạn rà lại từng ngoại lệ; xác minh before/after và outcome riêng. Chi tiết ở WORKFLOW và CONTRACTS §10a.
- Computer Use chỉ khởi tạo khi làm native; dispose/reset tác vụ/kernel sở hữu khi xong, chuyển backend/chờ/interrupt/terminal. Xác minh app/worker/pending input/capture; không kill tool server dùng chung. Quy trình đầy đủ ở WORKFLOW.

## Cập nhật tài liệu

Quyết định bền ghi một lần vào canonical owner và liên kết; AI_STATE thay thông tin cũ, không xếp chồng checkpoint. Ledger/history và chỉ mục cập nhật cùng thay đổi tài liệu. README là cửa vào sản phẩm; không dùng một bản 'latest' trong report cũ làm trạng thái hiện tại. Luồng đọc bắt buộc, retention và quyền đang mở không được suy ra từ snapshot lịch sử.
