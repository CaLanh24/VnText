<!-- Origin: docs/WORKFLOW.md at 242b5a97244234a4030a2ebf10bfa91ca72317cd; original section sha256 baeaefedf0058f5f200e533977692aae98f9cbf370e69e375924aa6758f19984. Authority preserved, latest Owner instructions prevail. -->

## Release và cập nhật

Phiên bản source lấy từ `VERSION.txt` cùng các version owner liên quan. Mỗi Setup/release cần evidence riêng từ đúng source, payload, hash và test của chính lần build đó; không suy ra phát hành từ tag dự kiến, metadata, mock hay artifact cục bộ.

Owner chọn dòng phiên bản public `0.1` (tag `v0.1`, source `0.1.0`); trạng thái giao bản và giới hạn kiểm chứng nằm trong `AI_STATE.md` và trang Release, không suy ra PASS từ tag. Offer/apply/restart stable GitHub 0.1.3 trên bản cài 0.1.2 đã PASS trong bounded scope; toàn product vẫn chưa `RELEASE_VERIFIED`. Người còn ở v0.1 dùng Setup 0.1.2; full-app update bắt đầu từ baseline mới theo `CONTRACTS.md` §10. Thay installer/uninstaller hoặc quyền hệ thống vẫn cần Setup mới. `Updates` cạnh Setup cục bộ không phải dịch vụ public update.

Không push, upload, tạo/xóa release hoặc thay đổi dịch vụ/dữ liệu ngoài repository nếu Owner chưa ủy quyền rõ cho task đó. Tuân thủ license, notices và provenance trong `THIRD_PARTY_NOTICES.md`; package metadata không tự chứng minh quyền phân phối.
