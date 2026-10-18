# Release 0.1.6 preparation

Owner requested public release on 2026-10-18 and waived further Cockpit motion comparison. Sole Coordinator/source writer continues the authorized dirty UI baseline on main. Scope: accepted UI, settings, icon/logo, update presentation and preference behavior; preserve worker protocol, engine behavior, validators and window ICO.

## Gates and budget

1. Inspect dependencies, source diff, version owners and third-party provenance; focused/affected tests, full regression with canonical cleanup.
2. Commit validated source/version/docs, then run exact-source Release gates. No prior DEV result is relabelled Release acceptance.
3. Build one candidate using preinstalled/explicitly approved dependencies; payload inventory, release verification, worker smoke in two cwd, mandatory GUI/install/upgrade/rollback checks before publishing.
4. Upload immutable Setup/provenance/checksums and applicable verified update asset only after gates. If no valid installed baseline exists, report Setup route explicitly rather than inventing update compatibility.

Initial inventory: non-exempt182,238,191bytes <=1GiB; shared .dev-env1,441,469,939bytes <=3GiB. No special0.1.5 quota/epoch approval is inherited. Project every payload phase before writing; stop if default cap cannot fit. One source snapshot/candidate maximum until evidence requires remediation; no game copies/campaign. TEST_RUN must end absent/empty; retain compact evidence in DEV_RUN/release-0.1.6. Source/runtime/fixture SHA and actual exits must be reported.

## Initial prerequisites

GitHub latest stable is v0.1.5 at source0e804cdfd05984aaeb2046b863cbe5f763bb8a04. Next patch is0.1.6. Current machine has .NET SDK8.0.426/runtime8.0.32 and Python3.14.8. Publisher requires SDK10 and Python3.12; no installed3.12 shown by py launcher. Permission requested for SDK10/Python3.12/requirements downloads into .dev-env; no dependency download or license acceptance until granted. Model files exist but distribution provenance still needs audit. No published0.1.6 candidate exists yet.

## Checkpoint / PROVEN_BLOCKED

Source version owners now0.1.6, no commit/push/release. Source-only8 tests PASS. Initial full discovery on dirty base0e804cdf:781tests,8failures,6errors,14skips; child/wrapper exit1, cleanupPASS, TEST_RUN absent. Failures include Windows short/long TEMP alias, long paths, cp1252 output and missing model default; absent SDK10/RenPy/installer/GUI prerequisites are explicit skips, not PASS. Do not relabel this as Release evidence. Next environment remediation: canonical redirected runtime TEMP/UTF8/model inputs and approved Python3.12/SDK10, then focused failed gates before exact-source full regression. No validator weakening or OS policy change.

DEV build initially failed due open own appPID7612 holding executable; normal native close released it. Final dev_bootstrap --action smoke --model .dev-env/cache/models/opus-mt-en-vi-int8 exit0 (fresh build/configured worker), source still dirty. Receipts: DEV_RUN/release-0.1.6/{source.log,full-regression.json,full-regression.log,build-locked.json,smoke-locked.json,dev-smoke-final.json}. No candidate writes or dependency downloads. Public release is blocked on missing Release dependencies/download authorization and failed full gate; consolidated approval question remains pending. Do not inherit Release0.1.5 artifact-budget exceptions.

## Owner dependency approval (2026-10-18)
Owner approved SDK10 and consolidated Python3.12/requirements downloads from official sources into .dev-env, preserving existing DEV environment. Local dependency installation only; no admin, OS settings or third-party license acceptance inferred. Resume release prerequisite remediation, no additional motion audit.

## Dependency admission checkpoint
SDK10.0.401 archive matched Microsoft SHA51224b670ad3d923bfcf47df6c3b034152398b42f6dbc388e10d783aee1cfb5e5817d399fc0ae2a12cfa822a55e61d34830ccb15c50ef6efee437ab874bb7c79430; extracted locally and downloaded archive removed. Python3.12.10 official PSF-signed installer exited0/no restart into .dev-env/python-3.12. DEV unchanged. Installation of requirements into fresh .dev-env/release-venv exceeded3GiB shared-environment cap (observed3,381,248,305bytes during install), so exact own pipPID14372 was identity-checked and stopped. Partial environment not accepted as usable. Attempted rollback of this exact new environment was rejected by automatic approval policy before execution; no alternate deletion attempted. Owner decision requested: increase shared .dev-env cap to5GiB, or retain3GiB and authorize cleanup of the newly created release-venv. Until then no further dependency writes/build/test payloads. Outcome PM_DECISION_REQUIRED. This quota admission mistake is recorded, not relabelled PASS. No source commit, push, upload or Release.

## Validated preparation / next exact-source gate
Owner explicitly approved temporary3GiB non-exempt artifact budget for exact release-0.1.6 candidate, reverting<=1GiB terminal; shared .dev-env5GiB. Canonical helper/publisher now admit separately approved0.1.6 epoch/scope without extending0.1.5 transition/rebaseline rights. Focused budget/publisher112PASS/wrapper0/cleanupPASS; parameterized0.1.5+0.1.6 epoch-registration/terminal-reversion testPASS. Earlier full precommit797tests/0fail/0error/13skip/warnings0, wrapper0/cleanupPASS. It predates new budget admission; final exact-source snapshot regression remains required. RenPy8.5.3 downloaded/hash-verified and installed under .dev-env/tools (receipt renpy-download.json); exact source run will enable native SDK gates. Long-path fixture/access remediation preserves registry/path/reparse guards, UTF8/explicit model/temp remove environment failures; Qt Pdf/WebEngine excluded from shipped worker. No game copies. Public0.1.6 still not released.
