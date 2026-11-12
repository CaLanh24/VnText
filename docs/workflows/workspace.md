<!-- Origin: docs/WORKFLOW.md at 242b5a97244234a4030a2ebf10bfa91ca72317cd; original section sha256 2d1af76d33a12d106703dec3ceff7bc7a1cf6987bb5b0e6ef02cfb1dc22f4703. Authority preserved, latest Owner instructions prevail. -->

## Quy tắc workspace và đường dẫn

Owner 2026-11-12: toàn bộ artifact, evidence, script tạm và cwd làm việc của dự án phải nằm trong checkout hiện hành (đường dẫn Owner chọn nằm ở AI_STATE). Không tạo lại root dự án ngoài checkout như vnrg/ctest. Profile/cấu hình của công cụ là application state riêng; không coi chúng là nơi chứa scratch dự án. Bằng chứng lịch sử chuyển về checkout phải giữ nguyên byte và có chỉ mục provenance, không sửa lịch sử để giả thành evidence mới.

- Dùng checkout/candidate root nông và tên scope/run ngắn, duy nhất; tránh clone lồng nhiều tầng, scope path lặp sâu và các thư mục `tmp` lồng nhau chỉ để né giới hạn đường dẫn hoặc quota.
- Trước validation hoặc allocation, kiểm độ sâu và đường dẫn tuyệt đối dài nhất cùng số entry/độ dài `PATH` ở Process/User/Machine. Không thêm các thư mục tạm lặp lại vào `PATH`; dùng `TEMP`/`TMP` ngắn, ổn định bên trong scope đã đăng ký cho lượt chạy và khôi phục sau đó. Không tự đổi biến môi trường User/Machine.
- Giữ repository portable: đường dẫn local do Owner chọn chỉ ghi trong `AI_STATE.md`/receipt phù hợp, không trở thành yêu cầu hardcode cho public clone.

Trước DEV validation hoặc game E2E, chốt scope, gate order, run/copy budget, executable provenance, prerequisite và cleanup theo `CONTRACTS.md` §10c; dùng `TEST_MATRIX.md` để chọn gate. Persist evidence từng bước trước bước phụ thuộc; outcome test và cleanup riêng.
