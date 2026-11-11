# Dependency profiles

`windows-cp312-runtime.txt` is the portable release worker profile; `windows-cp314-runtime.txt` is the existing DEV profile. Build profiles add PyInstaller only in an isolated builder environment. Install each with `python -m pip install --require-hashes -r <lock>`; build tooling is not part of the worker. Standard-library unittest needs no extra test package. Qt remains an optional compatibility extra in requirements-legacy-qt.txt, outside shipped WPF.

Each JSON records official artifact URL, SHA256, Python requirement and dependency metadata. Locks were resolved independently for each target, with six deliberately selected runtime roots matching the existing tested installation. They are not a freeze of all local packages. New-target import/native testing is separate from resolver success. No environment was upgraded by generating these locks.

`tpk_ar==0.2.4` publishes only a pure-Python source distribution. Its official sdist hash is locked; resolution used a wheel built locally from that source in disposable scratch. Builders must permit this specific source package and retain their build-isolation/tool provenance. Its locally built wheel hash is not distributed as though it were an official wheel. All other runtime entries pin a compatible official wheel. Never silently replace a hash or disable --require-hashes.

For an offline install, populate a verified wheelhouse ahead of time, retaining source-to-wheel build receipt for tpk_ar. .NET SDK/packs, embedded Python, RenPy SDK and model are separate acquired resources; Python locks do not assert their provenance or authorize downloads.

The `legacy-qt` profiles are optional Windows Qt dependencies only. publish.ps1 selects runtime/build/legacy-qt profiles through release/dependency_profiles.py, enforces hashes, and refuses unsupported profile/runtime or preinstalled-version drift. No Qt is selected for a normal WPF/worker build. Resolution/closure verification does not mean the publisher or every matrix installation was executed.
