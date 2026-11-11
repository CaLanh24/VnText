<!-- Origin: docs/WORKFLOW.md at 242b5a97244234a4030a2ebf10bfa91ca72317cd; original section sha256 e032d64dfc7178bb49e254f9ecbb348f8327d2c011ffb5c19800c7cc670ffa5e. Authority preserved, latest Owner instructions prevail. -->

## Invariants sản phẩm

- Workflow: extract → translate/import CSV → patch. Giữ key, schema/thứ tự CSV, manifest, locator, placeholder, tag, biến, newline, escape và engine boundary.
- Unity là engine đầu tiên, không có nghĩa hỗ trợ mọi game Unity. Chỉ quảng bá capability khi có extract, provenance, patch/write-back và verification tương ứng.
- Route dịch sản phẩm hiện là CTranslate2/OPUS-MT. Không khôi phục Argos hoặc VinAI nếu Owner chưa quyết định lại; Hy-MT2 chỉ test-only.
- Không đổi worker protocol, semantic workflow, game behavior, model, framework hay architecture nếu task không yêu cầu. Không hạ validator hoặc biến dữ liệu lỗi thành hợp lệ giả.
- Patch phải qua preflight/gate, backup và verification. Không thử trên game gốc hoặc dữ liệu user; test game chỉ dùng fixture/bản copy được khai báo.

