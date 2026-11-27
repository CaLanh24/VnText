# Release 0.1.39 — everything found by driving the real app, in one release

The Owner asked (chat, 2026-11-27) for one release that fixes everything still open instead of several small ones, and to drop the step numbers from the sidebar. The standing permission of 2026-11-25 applies. Task `release-0.1.39`, exact `RELEASE_RUN/candidate-0.1.39`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Changes
- **"Sửa tự động" / "Cài bộ dịch" can download the translator model.** The worker runs with `HF_HUB_OFFLINE=1`; only the explicit repair now lifts the offline switches (and restores them). Checked in the real app: model folder empty → button → 77,490,497 bytes downloaded, translator ready. The download size (≈75 MB model, ≈156 MB Ren'Py tools) is shown before the button is pressed.
- **After "Chấp nhận đề xuất" the row no longer keeps "bấm Lưu".** The editor validated before the save pruned the review ledger and showed that stale result; it now validates again after a successful save.
- **A translation waiting for review is a warning, not a red error.** The banner says the machine translation is done and names the next step (Sửa bản dịch → Thao tác → Chọn cần xem lại → Chấp nhận đề xuất / Sửa bản dịch / Bỏ qua dòng này).
- **No step numbers on the sidebar.** The four entries keep their order; a check mark follows the name once a step is done.
- **Wording:** "overlay" and "game root" replaced in the build result, "ngoài CSV" in the confirmation, the component-check failure no longer prints the .NET exception; every machine-translation check code has a Vietnamese label; "cần chú ý" instead of a second "cần xem lại" count.
- **Round-trip test fixture** no longer translates to CJK glyphs the bundled font lacks (`test_renpy_roundtrip` 7/7).
- **Dependency inventory** regenerated from the runtime lock (47 distributions).

## Checked in the real app (installed layout of 0.1.38 plus the fixed files, agent-desktop)
Model download; real translation with review on (4 rows → waiting); row detail with the machine proposal; "Chấp nhận đề xuất"; "Bỏ qua dòng này" with its confirmation; "Thao tác" menu; build confirmation and list of skipped lines; successful build; "Gửi báo lỗi" preview (answered "Không"; nothing sent); "Sửa tự động" installing the Ren'Py tools with the hash check.

## Not done
See `AI_STATE.md` for what was not run and why.

## Published
Tag `v0.1.39` = `30a630a47344fa2f5105303dff9680b3aed5b52e`; Setup sha256 `f517f99ae534331392eff3bc339d8c43420079dd000c143f0474e51ca4c8ee5c`; GitHub digests of the 5 assets equal the local files; update 0.1.38→0.1.39 read-back: 7341 files, 0 mismatches.
