"""Compatibility facade for split mt_ct2 responsibilities."""

from __future__ import annotations

from vntext import mt_ct2_constants as _constants

globals().update({name: value for name, value in vars(_constants).items() if not name.startswith('__')})

from vntext import mt_ct2_model as _mt_ct2_model
for _name in _mt_ct2_model.__all__:
    globals()[_name] = getattr(_mt_ct2_model, _name)

from vntext import mt_ct2_io as _mt_ct2_io
for _name in _mt_ct2_io.__all__:
    globals()[_name] = getattr(_mt_ct2_io, _name)

from vntext import mt_ct2_status as _mt_ct2_status
for _name in _mt_ct2_status.__all__:
    globals()[_name] = getattr(_mt_ct2_status, _name)

from vntext import mt_ct2_pipeline as _mt_ct2_pipeline
for _name in _mt_ct2_pipeline.__all__:
    globals()[_name] = getattr(_mt_ct2_pipeline, _name)

__all__ = [name for name in globals() if not name.startswith('_')]
