# Đề xuất khép font compatibility của RenPy — cần Owner mở phạm vi

## Quyết định đề nghị

Cho phép **một thử nghiệm overlay font riêng cho tiếng Việt trên bản copy game VM**, dùng font DejaVuSans đã có trong SDK. Chỉ chứng minh cách sửa cho game Owner cung cấp; chưa đưa thành tính năng/app mặc định. Không ghi đè font/script/RPA nguồn, không đổi font toàn app, không tải font, không đổi model hay behavior game. Phạm vi hiện hành cấm tự thay font; vì vậy đây là quyết định mở phạm vi cụ thể, chưa được áp dụng.

## Bằng chứng và nguyên nhân

- Run4 trên RPA gốc: normal Patch/full reextract/repatch PASS, Start và advance tới hai câu Việt PASS. Capture-only + fresh unique binding + activation phục hồi thành công. Câu dài xuống hai dòng không thấy clipping. Menu Load và cả hai câu có glyph sai; ảnh lỗi gốc được giữ nguyên.
- `gui.rpy` trong RPA, dòng61/64/67: `gui.text_font`, `gui.name_text_font`, `gui.interface_text_font` đều là `LumiosTypewriter-New_0.ttf`; style button/choice dùng các biến này. Audit source ngoài `tl` không thấy khai báo `config.replace_text`, `say_menu_text_filter`, `dialogue_filter` hay hook text_filter. Đây là static survey, không chứng minh mọi dynamic runtime hook đều vắng mặt.
- Font trong RPA: `fonts/LumiosTypewriter-New_0.ttf`,98388bytes/SHA256 `968b969e38cf7abcea8ebb723fd7d7d44bf316960be441932fa6ea32ce962269`. Unicode cmap4 trả glyph0 cho14/48codepoint cần trong năm target đã chốt: U+01B0ư,U+1EA3ả,U+1EA5ấ,U+1EA7ầ,U+1EABẫ,U+1EAFắ,U+1EB7ặ,U+1EBFế,U+1EC1ề,U+1EC9ỉ,U+1ED5ổ,U+1ED9ộ,U+1EDBớ,U+1EE9ứ. Đây là thiếu cmap xác định, không chỉ suy từ ảnh. Các font khác trong RPA cũng thiếu ký tự của mẫu.
- Five reviewed targets là Unicode UTF8 đúng trong receipt/provenance; normal Patch readback PASS. Actual overlay bytes/hash không được retain riêng trước cleanup run4, nên không gán hash giả cho file đã disposal. Native xuất đúng câu với glyph thay thế, trùng thiếu cmap; vẫn cần thử overlay để xác nhận remediation end-to-end, không mặc định PASS chỉ vì cmap đủ.
- `renpy-owner-font-audit.json` lưu exact declaration/line, codepoint→glyphID, hashes và required48codepoint. Audit đọc RAR/RPA streaming trong RAM, không extract thêm payload ra đĩa, không unpickle/execute game code. Bốn test focused PASS cho cmap4 delta/range-array,12/13groups, missingVN và bounds refusal; actual audit exit0/sourceRAR unchanged.

## Font có sẵn và license

`C:/Users/VNTextDev/source/VnText-v0.1.5/.dev-env/tools/renpy-8.5.3/renpy/common/DejaVuSans.ttf`:756072bytes, SHA256 `3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22`. Unicode cmap12 bao phủ48/48codepoint của mẫu; chưa phải bảo đảm mọi text tương lai/glyph shaping.

Notice có sẵn `DejaVuSans.txt`:4816bytes/SHA256 `d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e`. License BitstreamVera/Arev notices, DejaVu changes public domain; giữ nguyên đầy đủ notice với font không sửa. Không gọi đây là SIL/OFL. Local test không có upload/phát hành; nếu đưa vào product sau này cần cập nhật THIRD_PARTY_NOTICES theo owner đó.

Font+notice760888bytes, overlay/metadata dự kiến<16KiB: tổng tăng<1MiB, giữ peak measured run4 khoảng1.06GB dưới1GiB; vẫn đo lại trước mọi payload, không tự nâng cap hoặc xóa lịch sử. Không copy bundledruntime8.3.7; SDK8.5.3 qualification giữ nguyên.

## Phương án nhỏ nhất — thử VM trước

Owner sửa: chỉ `tests/tools/renpy_owner_rar_gate.py` và test/harness font liên quan. Thêm cờ opt-in defaultOFF, pin font/notice hash, sinh một profile trong registered disposable output. Không sửa production ở thử nghiệm này.

Artifact đề nghị: font+notice dưới `game/tl/vietnamese/_vntext_font/`, overlay cố định `game/tl/vietnamese/zzz_vntext_font_profile.rpy`, receipt ghi sourcefont/fallbackSHA, language và các style/GUI variable tác động. Dùng documented `translate vietnamese python` / `translate vietnamese style` để áp font cho text/name/interface/button/choice của đúng game; giữ nguyên text, tag, placeholder, size, outlines, callback và activation helper hiện có. Không dùng global font_replacement_map hoặc text replacement hook. Font có thể làm đổi bề rộng chữ; không tuyên bố layout giữ nguyên nếu chưa quan sát.

Local SDK docs: `doc/translation.html` §Style Translations mô tả language activation/reset/styles rebuild; `doc/text.html` §FontGroup mô tả fallback theo range. Toàn bộ typeface Việt sang DejaVu là phương án dễ kiểm đầu tiên; FontGroup chỉ thay glyph thiếu có thể giữ Latin gần kiểu cũ hơn nhưng cần thêm bold/italic/metrics proof, không chọn ngầm trong thử nghiệm.

Rollback chỉ file/profile do run sở hữu với hash/CAS, language-off phải về font gốc; không sửa/xóa original RPA/font. Nếu thử nghiệm xong, canonical disposal toàn copy sau ownedprocess exit. Không triển khai font hỗ trợ toàn app hay thêm manifest/worker protocol mới từ kết quả thử.

## Gate khi được phép

1. Focused: defaultOFF không tạo font artifact; exact source/font/notice hash mismatch từ chối; owned output only; profile compile với SDK; language-only reset/switch không tác động text/behavior; malformed font UNKNOWN thay vì tự PASS.
2. Một run5 riêng sau current capture prerequisite: cùng completegame subtree/fiveVIpairs, bình thường patch/readback/reextract/repatch; thêm declared opt-in profile; một native launch≤300s. Đối chiếu menu Start/Load/Save, hai câu Việt đủ48codepoint, wrap/no clipping, advance, đối chiếu language-off/original style nếu điều hướng an toàn. Không đi vào cảnh nhạy cảm để tìm choice; choice chưa đo trong game này phải ghi NOT_MEASURED.
3. Retain original screenshots và actual overlay/font hashes trước cleanup; originalRAR/RPA unchanged; quota/lifecycle riêng. Không rerun19/19+119 vì production chưa đổi. Native FAIL giữ nguyên, không sửa câu để né glyph.

## Product boundary và các route còn thiếu

Nếu thử VM PASS và Owner muốn thành capability của app, mới mở implementation riêng ở `vntext/patch_renpy.py` (owned font-profile payload/transaction/rollback), UI patch-profile owner và CONTRACTS/TEST_MATRIX/THIRD_PARTY_NOTICES tương ứng. Opt-in font compatibility preflight nên báo missing/UNKNOWN trước patch, không nới QA hoặc tự đổi gamefont. CSV schema/worker protocol/model/framework giữ nguyên trừ quyết định riêng.

OriginalRPA73rpy+73rpyc không phải purecompiled-only. Supplementary production inert reader trên nguyên bản `screens.rpyc` SHA `fadc20d18f3ca4613a65885c4f5299491ca9f756d2b9bbf6fb9dcb5d1a7782ae` từ runtime8.3.7 từ chối `Malformed mapping`; không unsafe fallback, không coi file/game hỏng, không tự gán compiled routePASS. Generated8.5.3 compiled fixtures vẫn bằng chứng riêng. PDLdialogue runtimeUNKNOWN và Aqua fontFAIL vẫn trong coverage matrix; không tự loại để đẹp số. Đề xuất này chỉ khép compatibility prerequisite có bằng chứng, chưa phải nghiệm thu mọi game hay purecompiled-only.

## Authorization clarification before trial
Brain directly reviewed this proposal/latestturn and clarified existing Owner local-extract/test + completion/necessaryactions authorization covers reversible harness-only disposableVM trial. Additional routine trial question was unnecessary; no silence-as-consent used. Proceed only defaultOFF/localcopy/language-only/pinned existingfont+notice/no originalRPA/source mutation/no redistribution/no production integration. Productdefaultfont/UI/capability decision remains unapproved. Nativeoutcome still pending; no overallverdict upgrade before review.
