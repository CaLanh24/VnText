# VNText Studio — Current contributor state

Updated: 2026-10-03. This short pointer is not release acceptance evidence.

- Product: WPF desktop application with a Python worker; CT2/OPUS-MT route.
- Source selection SHA: `72500b70dd19078a0a39aa68c45d716eb6368787`; published as
  a fresh 364-file public history at commit
  `a484c8e394b6d8d934da3ba270520791d92bdbc3`. Stable Setup baseline: 1.45.0.
- Apache-2.0 applies to VNText-owned source. Third-party packages and bundled
  components retain their own notices and conditional terms.
- Owner accepted Intel oneAPI terms for the identified Redistributables,
  including distributor obligations, on 2026-10-03. Other vendor rights or
  model/data rights are not inferred from that decision.
- Owner accepted the exact Setup 1.45.0 artifact, SHA-256
  `79d8bd223f94bc727f4e915580fdca7b331725fccbb407117bec9c2b072ada0a`,
  closing the manual UI gate for this Setup (Owner acceptance, not automated UI
  evidence). Stable releases: [v1.45.0](https://github.com/CaLanh24/VnText/releases/tag/v1.45.0)
  and [v1.45.1 WPF-only](https://github.com/CaLanh24/VnText/releases/tag/v1.45.1).
  The v1.45.1 package SHA-256 is
  `50eb2c9ac8fadbcd52521ace3ad7087b93edcbdb44652f7f8b0859d201186cac`; it
  updates the exact 1.45.0 baseline and does not change Setup/runtime/worker.
- Final suite: 778 tests, 0 failures/errors, 5 skips; wrapper outcome remains
  `CANCELLED` (`runner interrupted by keyboard interrupt`) and cleanup is
  independently `PASS`. Real installed-app GitHub update discovery/apply/
  rollback remains NOT VERIFIED; do not call this `RELEASE_VERIFIED`.
- Preserve extract → translate/import → validate/patch → read-back, user/game
  data, and fail-closed validation.
