"""Compatibility facade for split patch implementation."""

from __future__ import annotations

from vntext import patch_constants as _constants

globals().update({name: value for name, value in vars(_constants).items() if not name.startswith("__")})

from vntext import patch_plain as _patch_plain
for _name in _patch_plain.__all__:
    globals()[_name] = getattr(_patch_plain, _name)

from vntext import patch_unity as _patch_unity
for _name in _patch_unity.__all__:
    globals()[_name] = getattr(_patch_unity, _name)

from vntext import patch_naninovel as _patch_naninovel
for _name in _patch_naninovel.__all__:
    globals()[_name] = getattr(_patch_naninovel, _name)

from vntext import patch_output as _patch_output
for _name in _patch_output.__all__:
    globals()[_name] = getattr(_patch_output, _name)

from vntext import patch_safety as _patch_safety
for _name in _patch_safety.__all__:
    globals()[_name] = getattr(_patch_safety, _name)

from vntext import patch_pipeline as _patch_pipeline
for _name in _patch_pipeline.__all__:
    globals()[_name] = getattr(_patch_pipeline, _name)

__all__ = [name for name in globals() if not name.startswith('_')]
