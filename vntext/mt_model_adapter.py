"""Small model-adapter boundary for Local Translation V2.

The existing CT2 translator remains the default implementation.  This module
keeps model provenance and the narrow ``translate``/``translate_many`` surface
outside the translation pipeline so a future backend cannot bypass validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class TranslationModelAdapter(Protocol):
    """The only model surface the translation pipeline is allowed to call."""

    @property
    def config(self) -> dict[str, Any]: ...

    def translate(self, text: str) -> str: ...

    def translate_many(self, texts: list[str]) -> list[str]: ...

    def metadata(self) -> dict[str, Any]: ...


class Ct2ModelAdapter:
    """Adapter around the existing ``Ct2Translator`` implementation."""

    adapter_id = "ct2"
    model_id = "opus-mt-en-vi-ct2-int8"

    def __init__(self, translator: Any, model_dir: str | Path | None = None) -> None:
        self._translator = translator
        self._model_dir = str(Path(model_dir).resolve()) if model_dir else "default"

    @property
    def config(self) -> dict[str, Any]:
        value = getattr(self._translator, "config", {})
        return dict(value) if isinstance(value, dict) else value

    def translate(self, text: str) -> str:
        return str(self._translator.translate(text))

    def translate_many(self, texts: list[str]) -> list[str]:
        return [str(value) for value in self._translator.translate_many(texts)]

    def metadata(self) -> dict[str, Any]:
        config = self.config
        return {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "model_revision": self._model_dir,
            "model_path": self._model_dir,
            "model_engine": "CTranslate2/OPUS-MT",
            # Keep the inference contract in cache identity even though the
            # current backend uses ctranslate2's explicit API defaults.  A
            # future decoding change must deliberately change this profile
            # (and therefore invalidate validated candidates).
            "decoding": {
                "backend_api": "ctranslate2.translate_batch",
                "profile": "ct2-translate-batch-defaults-v1",
                "max_src_tokens": config.get("max_src_tokens"),
            },
        }


def adapt_ct2_translator(translator: Any, model_dir: str | Path | None = None) -> Ct2ModelAdapter:
    return Ct2ModelAdapter(translator, model_dir)


__all__ = ["TranslationModelAdapter", "Ct2ModelAdapter", "adapt_ct2_translator"]
