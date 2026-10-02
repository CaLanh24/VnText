"""Compatibility facade for the split extraction implementation.

Existing callers continue to import every extraction helper from this module.
"""

from __future__ import annotations

from vntext import extract_constants as _constants

globals().update({name: value for name, value in vars(_constants).items() if not name.startswith('__')})

from vntext import extract_quality as _extract_quality
for _name in _extract_quality.__all__:
    globals()[_name] = getattr(_extract_quality, _name)

from vntext import extract_text as _extract_text
for _name in _extract_text.__all__:
    globals()[_name] = getattr(_extract_text, _name)

from vntext import extract_naninovel as _extract_naninovel
for _name in _extract_naninovel.__all__:
    globals()[_name] = getattr(_extract_naninovel, _name)

from vntext import extract_unity as _extract_unity
for _name in _extract_unity.__all__:
    globals()[_name] = getattr(_extract_unity, _name)

from vntext import extract_postprocess as _extract_postprocess
for _name in _extract_postprocess.__all__:
    globals()[_name] = getattr(_extract_postprocess, _name)

from vntext import extract_pipeline as _extract_pipeline
for _name in _extract_pipeline.__all__:
    globals()[_name] = getattr(_extract_pipeline, _name)

__all__ = [name for name in globals() if not name.startswith('_')]
