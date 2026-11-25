# Dependency profiles

`windows-cp312-runtime.txt` is the portable release worker profile; `windows-cp314-runtime.txt` is the existing DEV profile. Install with `python -m pip install --require-hashes -r <lock>`. Standard-library unittest needs no extra test package. The former `build` (PyInstaller) and `legacy-qt` (PySide6) profiles were removed on 2026-11-25 together with the legacy Python UIs; publish.ps1 now needs only the runtime profile. `tests/unit/test_dependency_lock_closure.py` (public gate) re-verifies hash pairing, closure and that every `requirements.txt` root is locked.

Each JSON records official artifact URL, SHA256, Python requirement and dependency metadata. Locks were resolved independently for each target, with six deliberately selected runtime roots matching the existing tested installation. They are not a freeze of all local packages. New-target import/native testing is separate from resolver success. No environment was upgraded by generating these locks.

`tpk_ar==0.2.4` publishes only a pure-Python source distribution. Its official sdist hash is locked; resolution used a wheel built locally from that source in disposable scratch. Builders must permit this specific source package and retain their build-isolation/tool provenance. Its locally built wheel hash is not distributed as though it were an official wheel. All other runtime entries pin a compatible official wheel. Never silently replace a hash or disable --require-hashes.

For an offline install, populate a verified wheelhouse ahead of time, retaining source-to-wheel build receipt for tpk_ar. .NET SDK/packs, embedded Python, RenPy SDK and model are separate acquired resources; Python locks do not assert their provenance or authorize downloads.

publish.ps1 selects the runtime profile through release/dependency_profiles.py, enforces hashes, and refuses unsupported profile/runtime or preinstalled-version drift. Resolution/closure verification does not mean the publisher or every matrix installation was executed.
