# DEV VM pilot plan

## Owner decision — defer VM work

Recorded 2026-10-14. Do not provision or configure a VM yet. Finish the current VNText work and its release first. Once the repository is clean and the newest stable GitHub release has been read back and confirmed, review a concrete Phase 1 action plan. Phase 1 proves an empty persistent Windows guest and its isolation/persistence behavior. The later DEV bootstrap phase clones the exact confirmed public source/tag into that guest before installing the documented development environment. A local build or fixture is not the clone baseline.

This phase boundary does not authorize installing Hyper-V, changing host configuration, creating a VM, accepting new licenses, or downloading or installing software. Those actions need their own prerequisite and authorization review when Phase 1 begins.

## Product boundaries

- The goal is a persistent Windows DEV VM for the VNText source cloned from the confirmed release, including build, WPF and Computer Use work, with the development environment provisioned in later phases.
- Whether to use a particular account, model, user session, Brain setup, or DEV identity is a separate PM decision. Requiring two accounts, a particular model/session, or Brain/DEV account routing is not an entry gate for the VM plan.
- Installing the SDKs, Python dependencies, NuGet packages, and model dependencies required by VNText remains part of the later DEV bootstrap phase when that phase is authorized. Use the public development instructions and their provenance requirements; do not copy old-machine caches or private account/session material as a substitute.
- Guest activation is not a technical blocker for the pilot. Do not bypass activation or licensing controls. Longer-term product licensing is a separate PM decision.
- A VM result applies only to the exact guest configuration and source/tag tested. It does not establish broad hardware, account, model, or update coverage.

## Phase 1 entry evidence

Before any Phase 1 host/VM operation, review its exact action plan and record the clean source commit, stable release tag and Setup SHA-256 intended for the later clone, guest OS, VM owner/lifecycle, infrastructure budget and bounded acceptance plan. Phase 1 starts with an empty guest; cloning and DEV bootstrap happen only in their later phases. VHDX files and checkpoints use a separate infrastructure budget and a location approved by PM; they are not presumed to live in the repository or count against its 1 GiB/3 GiB artifact limits. Do not copy user game data, personal sessions, or private model/account material into the guest.

The ordering decision does not authorize implementation. After VNText is released, the repository is clean, and the newest stable release is confirmed, review the detailed Phase 1 action plan before executing it.

Historical preflight observation from before the 0.1.5 version checkpoint (2026-10-14): source version was 0.1.4, the checkout was dirty, no active prospective artifact epoch existed, the selected Python environment resolved to the Codex runtime, model revision/license provenance was unknown, NuGet readiness had not been exercised, and no installed 0.1.4 baseline copy was found. This paragraph records that earlier state; current release progress is tracked in AI_STATE.md. VM work has not started.
