# Cải thiện chất lượng dịch sau bản phát hành đang chuẩn bị

## Quyết định Owner — 2026-10-11

Hoãn đợt cải thiện chất lượng dịch và nghiên cứu huấn luyện tới sau khi phát hành bản đang chuẩn bị. Trước phát hành, ưu tiên chỉnh UI và luồng thông báo cập nhật theo `docs/UPDATE_UI.md`. Không mở chiến dịch model/huấn luyện song song với task UI/updater hoặc Release.

Đây là kế hoạch, chưa phải bằng chứng chất lượng hoặc quyền tải model, huấn luyện, thuê GPU hay sử dụng dữ liệu game. Version bản phát hành tiếp theo chưa được quyết định trong kế hoạch này.

## Premise hiện tại và giới hạn

- Route sản phẩm là CT2/OPUS-MT theo CONTRACTS §4/§4a; adapter, glossary, memory và cache đã tồn tại, cần tận dụng trước khi thêm hệ thống mới.
- Hai lượt kiểm game gần nhất chứng minh pipeline mẫu, không chứng minh chất lượng dịch toàn game. Evidence `DEV_RUN/two-game-report.md` tại checkpoint `3bbe595` ghi lỗi nghĩa như `sprang to my feet` và `Lewd Girl`; không đưa dữ liệu game riêng vào Git.
- QA cấu trúc và import Cloud Repair thành công không chứng minh bản dịch đúng nghĩa. Chỉ bản dịch đã được duyệt ngữ nghĩa mới có thể làm dữ liệu chuẩn.
- Context hiện là `METADATA_ONLY`; có sidecar không chứng minh model sử dụng ngữ cảnh hiệu quả. Memory/cache hợp lệ cấu trúc cũng không tự là dữ liệu đã duyệt ngữ nghĩa.
- Plan cũ và bài tham khảo chỉ là ý tưởng R&D. Danh sách model, phần cứng, tốc độ, giấy phép và benchmark lịch sử phải xác minh lại khi cần; không lấy lịch sử private làm prerequisite.

## 1. Bộ đánh giá và dữ liệu

Bắt đầu khoảng 100 câu EN→VI có quyền sử dụng, gồm hội thoại, thành ngữ, xưng hô, UI, thuật ngữ và protected tokens. Chốt người/quy trình duyệt ngữ nghĩa và tiêu chí đánh giá trước khi so sánh. Nếu chưa có người duyệt độc lập, báo rõ mức tin cậy; không gọi điểm tự chấm của model là human acceptance.

Tách dữ liệu phát triển và held-out đánh giá; không dùng các câu đã sửa để chứng minh khả năng tổng quát. Ghi nguồn, quyền sử dụng, phiên bản dữ liệu, engine/boundary/context khi có, bản dịch duyệt và loại lỗi. Không tự đưa game, CSV riêng hoặc dữ liệu người dùng vào Git/training. Không cần copy game chỉ để đánh giá các câu được phép sử dụng.

Đo sai nghĩa, bỏ/thêm ý, xưng hô, thuật ngữ và độ tự nhiên riêng với lỗi cấu trúc; giữ baseline OPUS và output trước/sau. Frozen benchmark 30 câu hiện có có thể tái sử dụng cho regression phù hợp, chưa đủ đại diện toàn sản phẩm.

## 2. Cải thiện route hiện có

Kiểm tác dụng glossary, bộ nhớ bản dịch đã duyệt và chuẩn hóa đầu vào theo lỗi có bằng chứng. So sánh baseline và từng thay đổi trên cùng held-out; không hardcode câu benchmark hoặc nới validator để tăng điểm.

Thu thập context chỉ khi có boundary đáng tin: cùng file/cảnh/nhóm, người nói và câu liền kề. Không đoán xuyên engine/file, không nối hội thoại vào CT2 rồi mặc định là dịch có ngữ cảnh. Chưa dựng vector database hoặc retrieval phức tạp nếu exact glossary/memory chưa cho thấy giới hạn cần giải quyết.

## 3. Một thử nghiệm model có ngữ cảnh

Khi bước 1–2 đã có kết quả, đề xuất tối đa một candidate đầu tiên, kiểm lại license, Windows/deployment và RAM/VRAM trên phần cứng thực. Owner duyệt model/download/quota trước thực thi.

So sánh dịch trực tiếp từ nguồn + context với sửa draft OPUS từ cùng nguồn + context trên cùng model và dữ liệu. Dịch trực tiếp là giả thuyết ưu tiên thử, không phải kết luận đã chứng minh. Giữ OPUS làm baseline/lựa chọn nhanh; không thay model sản phẩm chỉ vì một demo tốt.

## 4. Huấn luyện có điều kiện

Chỉ đề xuất pilot SFT/LoRA khi đã có corpus được duyệt, quyền sử dụng rõ và evidence cho thấy model candidate có triển vọng nhưng còn lỗi có thể học từ dữ liệu. Output teacher/cloud là draft cần duyệt, không tự là gold. Chốt ngân sách, môi trường, dung lượng và stop condition trước khi chạy; không mở hàng loạt model/training jobs.

Đánh giá trên held-out không lọt vào training; nếu không cải thiện đủ theo tiêu chí đã chốt thì dừng để xem lại premise/dữ liệu. Không tăng quy mô chỉ vì pilot chưa đạt.

## Acceptance và đóng từng đợt

Mỗi bước là một task bounded, một writer, theo AGENTS và CONTRACTS §10a/§10c. Trước task implementation, chốt phạm vi, gate, ngân sách run/copy/disk và tiêu chí cải thiện. Kết thúc phải có so sánh ngữ nghĩa, structural regression, latency/tài nguyên thực và giới hạn bằng chứng; cleanup riêng, một DEV executable khi sửa app. Không giữ bản sao game/model trùng lặp.

Candidate chỉ được promote khi cải thiện ngữ nghĩa trên nhóm mục tiêu, không có regression nghiêm trọng mới và mọi invariant cấu trúc/dữ liệu vẫn đạt. Ngưỡng và phạm vi hỗ trợ phải chốt trước thử nghiệm. Gate DEV không thay gate Release hoặc cập nhật trên bản cài thật.
