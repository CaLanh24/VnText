# Quyết định duyệt do Owner ủy quyền

Owner đã nói **“m duyệt đi”** tại chat Brain read-only, turn
`01a158d1-2185-7bc3-951f-1c82dc6c06af`. Brain chấp thuận cả17câu và6thuật ngữ
đúng đề xuất, nguồn, occurrence, ngữ cảnh và exclusions của gói gốc.
`decision.json` lưu đủ mapping cùng hash gói gốc, không sửa bất kỳ bản nháp,
manifest hay phiếu trống gốc nào.

Đây là **duyệt của agent được Owner ủy quyền**, không phải human linguistic gold,
không phải quyền training hoặc nghiệm thu chất lượng toàn app. TERM-014 được
chấp thuận cách chuyển câu bị động trong ngữ cảnh xuất dữ liệu; G05 chỉ được
dùng trong ngữ cảnh cache lookup/result, không phải mọi nghĩa của hit.

Chưa áp dụng vào app/package/memory. Bộ nhớ hiện tại có fallback theo
context-family và rebuild từ CSV có thể làm mất ranh giới scope: cần khép seam
này trước bước tích hợp. Không được biến các câu đã thấy thành bank mặc định.

Kiểm tra offline: `python -B -m tests.tools.translation_owner_approval verify`.
Verifier xác minh mapping/phạm vi/attribution của artifact, không tự tạo quyền,
duyệt ngôn ngữ lại hoặc xác nhận model đã cải thiện.

Brain đã nghiệm thu PASS phần strict-memory pilot theo
`scoped-delivery.json`:17/17tái dùng đúng scope, các ca sai scope/package không
tái dùng,161affected+14strict testsPASS và DEVsmoke/cleanupPASS. Đây chỉ là
syntheticpilot qua helper; chưa có entrypoint đại trà cho người dùng. Quyết định
gốc vẫn bất biến, không tự thay product_imported/training/human_gold flags.
