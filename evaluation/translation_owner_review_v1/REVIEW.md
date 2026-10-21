# Gói dịch/glossary chờ Owner duyệt

17 câu tổng hợp đã biết lỗi + 6 thuật ngữ. Tất cả **CHƯA DUYỆT**. Không inference mới, không ghi vào app/memory, không phải human gold hay cải thiện trên câu chưa thấy.

Duyệt từng ID (ví dụ: `Duyệt IDI-001, G01; sửa ADDR-016 thành …; từ chối G06`). Chỉ duyệt nghĩa/thuật ngữ cụ thể; không mặc nhiên duyệt triển khai, training, phạm vi toàn app hoặc giới tính chưa biết.

Có thể sao chép `owner-decisions.csv` để ghi quyết định; giữ bản gốc niêm phong. Các ô để trống, không có lựa chọn mặc định. Đây là phiếu review, không phải CSV import của app. `proposals.json` giữ provenance/ngữ cảnh gốc. Không tạo `.mt/translation_memory.json` hoặc bank mặc định.

Các câu đều do agent tạo cho dự án, lấy từ corpus đã thấy. Việc duyệt chỉ có giá trị trên đúng nguồn/ngữ cảnh/phạm vi được duyệt. Memory hiện có fallback trong cùng package, chưa bảo đảm khóa cứng theo file/cảnh; chưa tự chuyển các đề xuất này thành memory.

## IDI-001

**Nguồn:** Mara nearly spilled the beans about the surprise.

**OPUS đã quan sát:** Mara Suýt nữa thì làm đổ đậu ra vì bất ngờ.

**Đề xuất:** Mara suýt để lộ bí mật về điều bất ngờ ấy.

**Cần duyệt:** spill the beans = để lộ bí mật; nearly chỉ suýt, chưa xác nhận đã lộ.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-001: Mara nearly spilled the beans about the surprise.; IDI-002: The secret came out of the bag when the curtain fell.

**Phạm vi đề xuất:** `synthetic/idioms/scene-01` / `idioms-scene-01`, đúng câu nguồn; chưa áp dụng.

## IDI-004

**Nguồn:** At the next village, we can call it a day.

**OPUS đã quan sát:** Ở làng kế bên, chúng ta có thể gọi đó là một ngày.

**Đề xuất:** Đến ngôi làng tiếp theo, chúng ta có thể nghỉ thôi.

**Cần duyệt:** call it a day = dừng công việc/chặng đi hôm nay; không phải đặt tên một ngày. Không thêm kế hoạch ngày mai.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-003: We should hit the road before the bridge closes.; IDI-004: At the next village, we can call it a day.

**Phạm vi đề xuất:** `synthetic/idioms/scene-02` / `idioms-scene-02`, đúng câu nguồn; chưa áp dụng.

## IDI-005

**Nguồn:** For Lin, the first puzzle was a piece of cake.

**OPUS đã quan sát:** Cho Lin Câu đố đầu tiên là một miếng bánh.

**Đề xuất:** Với Lin, câu đố đầu tiên dễ như ăn kẹo.

**Cần duyệt:** piece of cake = rất dễ; giữ tên Lin, không tự gán giới tính.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-005: For Lin, the first puzzle was a piece of cake.; IDI-006: The next riddle made her bite the bullet and ask for a hint.

**Phạm vi đề xuất:** `synthetic/idioms/scene-03` / `idioms-scene-03`, đúng câu nguồn; chưa áp dụng.

## IDI-006

**Nguồn:** The next riddle made her bite the bullet and ask for a hint.

**OPUS đã quan sát:** Câu đố tiếp theo khiến cô ta cắn viên đạn và hỏi ý kiến.

**Đề xuất:** Câu đố tiếp theo khiến cô ấy phải cắn răng xin gợi ý.

**Cần duyệt:** bite the bullet = chấp nhận làm việc khó/ngại; her cho phép cô ấy. Xin duyệt sắc thái cắn răng.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-005: For Lin, the first puzzle was a piece of cake.; IDI-006: The next riddle made her bite the bullet and ask for a hint.

**Phạm vi đề xuất:** `synthetic/idioms/scene-03` / `idioms-scene-03`, đúng câu nguồn; chưa áp dụng.

## IDI-007

**Nguồn:** I feel under the weather after standing in the cold rain.

**OPUS đã quan sát:** Tôi cảm thấy dưới thời tiết sau khi đứng trong cơn mưa giá lạnh.

**Đề xuất:** Tôi thấy trong người không khỏe sau khi đứng dưới mưa lạnh.

**Cần duyệt:** under the weather = không khỏe; không tự chẩn đoán bệnh cụ thể.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-007: I feel under the weather after standing in the cold rain.; IDI-008: I am not out of the woods until the fever is gone.

**Phạm vi đề xuất:** `synthetic/idioms/scene-04` / `idioms-scene-04`, đúng câu nguồn; chưa áp dụng.

## IDI-010

**Nguồn:** Even so, its repair cost an arm and a leg.

**OPUS đã quan sát:** Dù vậy, việc sửa chữa của nó cũng tốn cả một cánh tay và một chân.

**Đề xuất:** Dù vậy, việc sửa nó vẫn tốn một khoản tiền rất lớn.

**Cần duyệt:** an arm and a leg = rất tốn tiền; its giữ liên hệ vật ở câu cùng cảnh, không tự đổi vật.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-009: The old radio works only once in a blue moon.; IDI-010: Even so, its repair cost an arm and a leg.

**Phạm vi đề xuất:** `synthetic/idioms/scene-05` / `idioms-scene-05`, đúng câu nguồn; chưa áp dụng.

## IDI-012

**Nguồn:** I will take that promise with a grain of salt until the repair is done.

**OPUS đã quan sát:** Tôi sẽ thực hiện lời hứa đó với một hạt muối cho đến khi sửa chữa xong.

**Đề xuất:** Tôi sẽ còn hoài nghi lời hứa đó cho đến khi việc sửa chữa hoàn tất.

**Cần duyệt:** grain of salt = chưa hoàn toàn tin; giữ mốc until, không khẳng định lời hứa chắc chắn sai.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-011: We need to be on the same page before signing the lease.; IDI-012: I will take that promise with a grain of salt until the repair is done.

**Phạm vi đề xuất:** `synthetic/idioms/scene-06` / `idioms-scene-06`, đúng câu nguồn; chưa áp dụng.

## IDI-015

**Nguồn:** Please do not let the cat out of the bag before her birthday.

**OPUS đã quan sát:** Xin đừng để con mèo ra khỏi túi trước sinh nhật nó.

**Đề xuất:** Xin đừng để lộ bí mật trước sinh nhật của cô ấy.

**Cần duyệt:** let the cat out of the bag = để lộ bí mật; giữ phủ định và before.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-015: Please do not let the cat out of the bag before her birthday.

**Phạm vi đề xuất:** `synthetic/idioms/standalone-15` / `idioms-standalone-15`, đúng câu nguồn; chưa áp dụng.

## IDI-016

**Nguồn:** The patient was out of the woods after the fever broke.

**OPUS đã quan sát:** Bệnh nhân đã ra khỏi rừng sau khi cơn sốt tan.

**Đề xuất:** Bệnh nhân đã qua cơn nguy hiểm sau khi hạ sốt.

**Cần duyệt:** out of the woods trong ngữ cảnh sốt = hết nguy hiểm; không khẳng định đã khỏi bệnh hoàn toàn.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-016: The patient was out of the woods after the fever broke.

**Phạm vi đề xuất:** `synthetic/idioms/standalone-16` / `idioms-standalone-16`, đúng câu nguồn; chưa áp dụng.

## IDI-017

**Nguồn:** The gutters overflow because it is raining cats and dogs outside.

**OPUS đã quan sát:** Những máng nước tràn ngập bởi vì nó là những con mèo và những con chó ở bên ngoài.

**Đề xuất:** Máng xối bị tràn vì ngoài trời đang mưa như trút nước.

**Cần duyệt:** raining cats and dogs = mưa rất to; giữ quan hệ vì và địa điểm ngoài trời.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** IDI-017: The gutters overflow because it is raining cats and dogs outside.

**Phạm vi đề xuất:** `synthetic/idioms/standalone-17` / `idioms-standalone-17`, đúng câu nguồn; chưa áp dụng.

## ADDR-008

**Nguồn:** I will send the corrected page as soon as I return.

**OPUS đã quan sát:** Tôi sẽ gửi ngay khi tôi trở về.

**Đề xuất:** Ngay khi trở lại, tôi sẽ gửi trang đã chỉnh sửa.

**Cần duyệt:** Nhân viên nói với quản lý: giữ đối tượng trang đã sửa và as soon as; tôi không gán giới tính quản lý.

**Quan hệ nhân vật (metadata gốc):** A direct report speaks professionally to a manager.

**Cùng cảnh/tài liệu:** ADDR-007: Could I review the schedule with you after lunch?; ADDR-008: I will send the corrected page as soon as I return.

**Phạm vi đề xuất:** `synthetic/address/scene-04` / `address-scene-04`, đúng câu nguồn; chưa áp dụng.

## ADDR-014

**Nguồn:** You can tell me the truth; I will not be angry with you.

**OPUS đã quan sát:** Ngươi có thể nói thật, ta sẽ không giận ngươi đâu.

**Đề xuất:** Em có thể nói thật với chị; chị sẽ không giận em đâu.

**Cần duyệt:** Metadata gốc: chị gái nói dịu dàng với em trai. Chị/em có căn cứ; giữ cho phép và sẽ không giận.

**Quan hệ nhân vật (metadata gốc):** An older sister speaks gently to her younger brother.

**Cùng cảnh/tài liệu:** ADDR-014: You can tell me the truth; I will not be angry with you.; ADDR-015: We have known each other too long for that excuse.

**Phạm vi đề xuất:** `synthetic/address/scene-07` / `address-scene-07`, đúng câu nguồn; chưa áp dụng.

## ADDR-015

**Nguồn:** We have known each other too long for that excuse.

**OPUS đã quan sát:** Chúng ta đã biết nhau quá lâu rồi.

**Đề xuất:** Chị em mình đã biết nhau lâu đến thế rồi, cái cớ đó không thuyết phục đâu.

**Cần duyệt:** Cùng chị gái/em trai ở câu trước; diễn đạt ý bác cái cớ. Không thêm mệnh lệnh hoặc biến thành chỉ nói quen lâu.

**Quan hệ nhân vật (metadata gốc):** An older sister speaks gently to her younger brother.

**Cùng cảnh/tài liệu:** ADDR-014: You can tell me the truth; I will not be angry with you.; ADDR-015: We have known each other too long for that excuse.

**Phạm vi đề xuất:** `synthetic/address/scene-07` / `address-scene-07`, đúng câu nguồn; chưa áp dụng.

## ADDR-016

**Nguồn:** Professor, would you look over the last page when you have a moment?

**OPUS đã quan sát:** Giáo sư, ông có thể xem qua trang cuối cùng khi có thời gian không?

**Đề xuất:** Thưa giáo sư, khi nào có thời gian, xin xem giúp trang cuối.

**Cần duyệt:** Học viên cao học nói kính trọng với giáo sư lớn tuổi. Giới tính UNKNOWN: tránh ông/bà/thầy/cô; không tự chọn giới tính.

**Quan hệ nhân vật (metadata gốc):** A graduate student speaks respectfully to an older professor.

**Cùng cảnh/tài liệu:** ADDR-016: Professor, would you look over the last page when you have a moment?; ADDR-017: I can revise it this evening if you think it needs more work.

**Phạm vi đề xuất:** `synthetic/address/scene-08` / `address-scene-08`, đúng câu nguồn; chưa áp dụng.

## TERM-001

**Nguồn:** The patch manifest lists every source file and its checksum.

**OPUS đã quan sát:** Bảng liệt kê mọi tập tin nguồn và hệ thống kiểm tra.

**Đề xuất:** Bản kê khai của bản vá liệt kê mọi tệp nguồn cùng mã kiểm tra của từng tệp.

**Cần duyệt:** Giữ patch, manifest, mọi source file và checksum ứng với từng tệp. Mã kiểm tra là thuật ngữ đề xuất, chưa duyệt.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** TERM-001: The patch manifest lists every source file and its checksum.; TERM-002: A locator identifies the exact text field that can be written back.

**Phạm vi đề xuất:** `synthetic/terms/note-01` / `terms-note-01`, đúng câu nguồn; chưa áp dụng.

## TERM-004

**Nguồn:** A cache hit must pass validation again before it can be reused.

**OPUS đã quan sát:** Cần phải thông qua lại một lần nữa trước khi dùng lại bộ nhớ tạm.

**Đề xuất:** Kết quả tìm thấy trong bộ nhớ đệm phải được kiểm tra tính hợp lệ một lần nữa trước khi dùng lại.

**Cần duyệt:** Nguồn dùng cache hit/it cho kết quả cache; đề xuất làm rõ kết quả, không biến validation thành đăng nhập/xác thực danh tính. Cần duyệt cách diễn đạt.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** TERM-003: The package keeps review-only entries outside the patchable set.; TERM-004: A cache hit must pass validation again before it can be reused.

**Phạm vi đề xuất:** `synthetic/terms/note-02` / `terms-note-02`, đúng câu nguồn; chưa áp dụng.

## TERM-014

**Nguồn:** The export stores its manifest beside the translation table in one package.

**OPUS đã quan sát:** Xuất khẩu lưu trữ bản kê khai bên cạnh bảng dịch trong một gói.

**Đề xuất:** Khi xuất, bản kê khai được lưu cạnh bảng dịch trong cùng một gói.

**Cần duyệt:** export là thao tác xuất dữ liệu, không phải thương mại; giữ beside và one package. Cần duyệt cách chuyển câu sang bị động.

**Quan hệ nhân vật (metadata gốc):** UNKNOWN / not supplied

**Cùng cảnh/tài liệu:** TERM-013: A stable key keeps the same source row identifiable after CSV reordering.; TERM-014: The export stores its manifest beside the translation table in one package.

**Phạm vi đề xuất:** `synthetic/terms/note-07` / `terms-note-07`, đúng câu nguồn; chưa áp dụng.

## Thuật ngữ — đều chờ duyệt

| ID | Nguồn → đề xuất | Phạm vi / không áp dụng |
| --- | --- | --- |
| G01 | checksum → mã kiểm tra | TERM-001. Giá trị kiểm tra đi kèm tệp; không tự gán thuật toán/hash mật mã. Không áp cho dấu tick, kiểm tra thủ công hoặc mã đăng nhập. |
| G02 | manifest → bản kê khai | TERM-001, TERM-014. Danh mục tệp/metadata trong gói hoặc bản vá. Không áp cho manifest động từ: biểu lộ, hay ngữ cảnh vận đơn chưa được duyệt. |
| G03 | patch → bản vá | TERM-001. Gói thay đổi phần mềm. Không áp cho miếng vá quần áo/vùng đất/động từ chữa lành. |
| G04 | cache → bộ nhớ đệm | TERM-004. Dữ liệu đã lưu để dùng lại trong phần mềm. Không áp cho chỗ giấu đồ trong game; không đồng nhất với translation memory. |
| G05 | cache hit → tìm thấy trong bộ nhớ đệm | TERM-004. Sự kiện tìm thấy dữ liệu; toàn câu dùng kết quả tìm thấy để xử lý it. Không thay mọi hit thành tìm thấy; không dùng cụm này thay toàn câu. |
| G06 | export → xuất | TERM-014. Thao tác tạo gói dữ liệu xuất. Không áp cho xuất khẩu thương mại. Cấu trúc danh từ/động từ phải duyệt cả câu. |

Không dùng idiom như glossary thay từ toàn cục: các bản diễn đạt thành ngữ ở trên là đề xuất cả câu, có ngữ cảnh. Sau phản hồi Owner mới xác định ID được duyệt và gate tích hợp tương ứng.
