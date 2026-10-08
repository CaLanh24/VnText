# Trạng thái hiện tại — VNText Studio

## Public 0.1.4

Stable Release: https://github.com/CaLanh24/VnText/releases/tag/v0.1.4. Artifact/tag source `53a4ce97d6ee90a8627cf870839aa1d5c4f6865d`; docs receipt HEAD `4a173d7` không relabel evidence theo HEAD mới.
Setup SHA256 `ad3415483fd6abd4c6e25c2911a671638209664ac768b93a22734d806d486691`; full-app SHA256 `117bd47a37476aea6a6a198698e993b98db37aea9a0de1b7cda489da63175c0b`, baseline0.1.3. Publication read-back xác nhận flags/size/digest; installed stable0.1.4 acceptance và toàn product `RELEASE_VERIFIED` vẫn NOT VERIFIED.
Gates source53a4ce9: focused WPF7/7, version4/4, full679/0failure/0error/7skip, child/wrapper0; publisher/verify/smoke/payload/cleanup PASS. Skip2 installer chưa build trong full,1 legacy Tk,4 external Unity opt-in. Đây là evidence trước remediation.

## Audit 2026-10-08 và remediation DEV

Audit report: `RELEASE_RUN/audit-2026-10-08.md`; latest publish EXE raw smoke: `RELEASE_RUN/audit-latest-smoke.stdout.txt`/stderr. Smoke native0 với runtime8 tại Program Files; GUI HWND/normal-close quan sát, chưa kiểm đầy đủ pixel/interaction.
Game campaign đã tiêu thụ lượt: Unity extract27767rows, translate timeout300s/exit1; RenPy raw completion mất nên UNKNOWN. Extra game copy và game-before-non-game là sai lệch audit. Không chứng minh root cause sản phẩm hoặc full-game read-back; fixture/payload đã dọn, không rerun.
Remediation dùng `release/dev_bootstrap.py` và output owner `DEV_RUN/bootstrap-build`; receipt/runtime/source/hash/smoke được giữ trong build-identity.json, smoke.json và `DEV_RUN/remediation-build.json`. Luật bền vững ở CONTRACTS§10c, gate ở TEST_MATRIX, thao tác ở docs/DEVELOPMENT.
`TEST_RUN` còn11file/2646021bytes registry/epoch/reports trước task. Disposition phải giữ ledger/rollback/evidence và được cho phép trước khi disposal; không có whole-root delete authority. `.dev-env`/data/model/executable cũ giữ nguyên nếu ownership xử lý chưa đủ.