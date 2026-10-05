"""Model responsibilities split from mt_ct2."""

from __future__ import annotations

from vntext.mt_ct2_constants import (
    CT2_MAX_SRC_TOKENS,
    MODEL_REPO,
    MODEL_REVISION,
    MODEL_SUBDIR,
    Path,
    _SENTENCE_SPLIT_RX,
    _SENTINEL_KEEP_RX,
    _SOFT_SPLIT_RX,
    _TRANSLATOR,
    _TRANSLATOR_DIR,
    _TRANSLATOR_LOCK,
    os,
)



class MtCt2Error(Exception):
    pass


class ModelNotReadyError(MtCt2Error):
    pass


class EmptyCsvError(MtCt2Error):
    pass


class TranslateCancelled(MtCt2Error):
    pass


def _default_inter_threads() -> int:
    raw = os.environ.get("VNTEXT_CT2_INTER_THREADS", "").strip()
    if raw:
        return max(1, int(raw))
    return min(8, os.cpu_count() or 4)


def _default_batch_size() -> int:
    raw = os.environ.get("VNTEXT_CT2_BATCH_SIZE", "").strip()
    if raw:
        return max(1, int(raw))
    return 256


def _flush_every_rows() -> int:
    raw = os.environ.get("VNTEXT_CT2_FLUSH_EVERY", "").strip()
    if raw:
        return max(64, int(raw))
    return 256


def _fast_retry_default(n_targets: int) -> bool:
    """Job rất lớn: retry nhẹ. Job vừa/nhỏ (vòng sau): full strategies."""
    env = os.environ.get("VNTEXT_CT2_FAST_RETRY", "").strip().lower()
    if env in ("0", "false", "no"):
        return False
    if env in ("1", "true", "yes"):
        return True
    return n_targets >= 12000


def _split_text_under_token_limit(
    text: str,
    tok_len_fn,
    *,
    max_tokens: int = CT2_MAX_SRC_TOKENS,
) -> list[str]:
    """Chia text dài thành phần <= max_tokens; join(parts) == text (không cắt mất ký tự)."""
    if not text:
        return [text]
    if tok_len_fn(text) <= max_tokens:
        return [text]

    def _pieces_from_pattern(src: str, pattern: re.Pattern) -> list[str] | None:
        parts: list[str] = []
        last = 0
        for m in pattern.finditer(src):
            end = m.end()
            if end <= last:
                continue
            parts.append(src[last:end])
            last = end
        if last < len(src):
            parts.append(src[last:])
        if len(parts) <= 1:
            return None
        if "".join(parts) != src:
            return None
        return parts

    def _atomic_spans(src: str) -> list[str]:
        """Giữ nguyên từng sentinel ZZG#ZZG như khối không tách."""
        parts: list[str] = []
        last = 0
        for m in _SENTINEL_KEEP_RX.finditer(src):
            if m.start() > last:
                parts.append(src[last : m.start()])
            parts.append(m.group(0))
            last = m.end()
        if last < len(src):
            parts.append(src[last:])
        return parts or [src]

    def _pack(pieces: list[str]) -> list[str]:
        packed: list[str] = []
        buf = ""
        for piece in pieces:
            candidate = buf + piece
            if buf and tok_len_fn(candidate) > max_tokens:
                packed.append(buf)
                buf = piece
            else:
                buf = candidate
        if buf:
            packed.append(buf)
        return packed

    def _finish(pieces: list[str]) -> list[str] | None:
        packed = _pack(pieces)
        if all(tok_len_fn(p) <= max_tokens for p in packed) and "".join(packed) == text:
            return packed
        out: list[str] = []
        for p in packed:
            if tok_len_fn(p) <= max_tokens:
                out.append(p)
                continue
            if _SENTINEL_KEEP_RX.fullmatch(p):
                # Sentinel đơn lẻ vẫn vượt budget — không cắt; caller phải bỏ strategy.
                return None
            sub = _split_text_under_token_limit(p, tok_len_fn, max_tokens=max_tokens)
            if "".join(sub) != p:
                return None
            out.extend(sub)
        if "".join(out) == text and all(tok_len_fn(p) <= max_tokens for p in out):
            return out
        return None

    # Ưu tiên tách quanh sentinel (giữ khối ZZG nguyên), rồi câu, rồi khoảng trắng.
    atoms = _atomic_spans(text)
    if len(atoms) > 1:
        refined: list[str] = []
        for atom in atoms:
            if _SENTINEL_KEEP_RX.fullmatch(atom) or tok_len_fn(atom) <= max_tokens:
                refined.append(atom)
            else:
                for pattern in (_SENTENCE_SPLIT_RX, _SOFT_SPLIT_RX):
                    sub = _pieces_from_pattern(atom, pattern)
                    if sub:
                        refined.extend(sub)
                        break
                else:
                    refined.append(atom)
        done = _finish(refined)
        if done:
            return done

    for pattern in (_SENTENCE_SPLIT_RX, _SOFT_SPLIT_RX):
        pieces = _pieces_from_pattern(text, pattern)
        if not pieces:
            continue
        done = _finish(pieces)
        if done:
            return done

    # Hard split theo ký tự; không cắt giữa sentinel.
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        # Nếu đang đứng đầu sentinel, lấy cả sentinel (hoặc fail nếu quá dài).
        sm = _SENTINEL_KEEP_RX.match(text, i)
        if sm:
            chunk = sm.group(0)
            if tok_len_fn(chunk) > max_tokens:
                # Không thể chia an toàn — trả nguyên text để caller phát hiện/bỏ strategy.
                return [text]
            out.append(chunk)
            i = sm.end()
            continue
        lo, hi = 1, n - i
        best = 1
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = text[i : i + mid]
            # Không để phần kết thúc cắt giữa sentinel.
            cut = mid
            for m in _SENTINEL_KEEP_RX.finditer(candidate):
                if m.end() == len(candidate):
                    break
                if m.start() < len(candidate) <= m.end():
                    cut = m.start()
                    break
            else:
                # Kiểm tra sentinel bắt đầu gần cuối và kéo sang phần sau.
                tail = text[i : i + mid + 16]
                for m in _SENTINEL_KEEP_RX.finditer(tail):
                    if m.start() < mid < m.end():
                        cut = m.start()
                        break
            if cut < 1:
                cut = 1
            if tok_len_fn(text[i : i + cut]) <= max_tokens:
                best = cut
                lo = mid + 1
            else:
                hi = mid - 1
        out.append(text[i : i + best])
        i += best
    if "".join(out) != text:
        return [text]
    # Nếu vẫn có phần vượt limit (sentinel quá dài), trả nguyên để không cắt nội dung.
    if any(tok_len_fn(p) > max_tokens for p in out):
        return [text]
    return out or [text]


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    if here.name == "vntext" and (here.parent / "vntext_worker").is_dir():
        return here.parent
    return here.parent


def resolve_model_dir(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("VNTEXT_CT2_MODEL", "").strip()
    if env:
        return Path(env)
    work_model = _repo_root() / ".dev-env" / "cache" / "models" / MODEL_SUBDIR
    if (work_model / "model.bin").is_file():
        return work_model
    release_model = _repo_root() / "models" / MODEL_SUBDIR
    if (release_model / "model.bin").is_file():
        return release_model
    from vntext.runtime_paths import app_data_root

    return app_data_root() / "models" / MODEL_SUBDIR


def ensure_model(model_dir: Path | None = None, *, download: bool = True) -> Path:
    target = model_dir or resolve_model_dir()
    if (target / "model.bin").is_file():
        return target
    if not download:
        raise ModelNotReadyError(f"CTranslate2 model not found: {target}")
    if os.environ.get("VNTEXT_CT2_NO_DOWNLOAD", "").strip().lower() in ("1", "true", "yes"):
        raise ModelNotReadyError(f"CTranslate2 model not found (download disabled): {target}")
    target.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_REVISION,
            local_dir=str(target),
        )
    except Exception as exc:
        raise ModelNotReadyError(f"cannot download model: {exc}") from exc
    if not (target / "model.bin").is_file():
        raise ModelNotReadyError(f"model.bin missing after download: {target}")
    return target


class Ct2Translator:
    def __init__(self, model_dir: Path) -> None:
        import ctranslate2
        from transformers import MarianTokenizer

        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        inter = _default_inter_threads()
        intra = int(os.environ.get("VNTEXT_CT2_INTRA_THREADS", "1") or "1")
        self._batch_size = _default_batch_size()
        self._max_batch_size = max(32, int(os.environ.get("VNTEXT_CT2_MAX_BATCH_SIZE", "2048") or "2048"))
        self._max_src_tokens = CT2_MAX_SRC_TOKENS
        self._inter_threads = inter
        self._intra_threads = intra
        self._translator = ctranslate2.Translator(
            str(model_dir),
            device="cpu",
            inter_threads=inter,
            intra_threads=intra,
        )
        self._tokenizer = MarianTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        self._target_prefix = self._resolve_target_prefix()

    @property
    def config(self) -> dict[str, int]:
        return {
            "batch_size": self._batch_size,
            "max_batch_size": self._max_batch_size,
            "max_src_tokens": self._max_src_tokens,
            "inter_threads": self._inter_threads,
            "intra_threads": self._intra_threads,
        }

    def _token_len(self, text: str) -> int:
        tok = self._tokenizer
        ids = tok.encode(text or "", add_special_tokens=True)
        return len(ids)

    def _resolve_target_prefix(self) -> str:
        """Return a model-declared Marian target token, if this model needs one."""
        target = str(getattr(self._tokenizer, "target_lang", "") or "").strip()
        if not target:
            return ""
        token = f">>{target}<<"
        get_vocab = getattr(self._tokenizer, "get_vocab", None)
        if not callable(get_vocab):
            return ""
        try:
            return token if token in get_vocab() else ""
        except Exception:
            return ""

    def _model_input(self, text: str) -> str:
        value = str(text or "")
        prefix = str(getattr(self, "_target_prefix", "") or "")
        if not prefix or value.lstrip().startswith(prefix):
            return value
        return f"{prefix} {value}"

    def _input_token_len(self, text: str) -> int:
        return self._token_len(self._model_input(text))

    def translate(self, text: str) -> str:
        results = self.translate_many([text])
        return results[0] if results else (text or "")

    def _translate_token_batch(self, texts: list[str]) -> list[str]:
        """Dịch list text đã đảm bảo mỗi phần <= max_src_tokens."""
        if not texts:
            return []
        tok = self._tokenizer
        out: list[str] = []
        for start in range(0, len(texts), self._batch_size):
            chunk = texts[start : start + self._batch_size]
            active_idx = [i for i, t in enumerate(chunk) if (t or "").strip()]
            if not active_idx:
                out.extend(chunk)
                continue
            active_texts = [chunk[i] for i in active_idx]
            # encode từng câu (khớp _token_len) — tránh warning HF khi batch pad chuỗi >512.
            src_tokens = [
                tok.convert_ids_to_tokens(tok.encode(t or "", add_special_tokens=True))
                for t in active_texts
            ]
            safe_idx = []
            safe_tokens = []
            translated_active: list[str | None] = [None] * len(active_texts)
            for i, tokens in enumerate(src_tokens):
                if len(tokens) <= self._max_src_tokens:
                    safe_idx.append(i)
                    safe_tokens.append(tokens)
                    continue
                # Còn vượt budget: tách chặt hơn rồi dịch từng phần (không truncate mất chữ).
                tight = max(64, self._max_src_tokens - 32)
                parts = _split_text_under_token_limit(
                    active_texts[i], self._token_len, max_tokens=tight
                )
                if (
                    len(parts) > 1
                    and "".join(parts) == active_texts[i]
                    and all(self._token_len(p) <= self._max_src_tokens for p in parts)
                ):
                    translated_active[i] = "".join(self._translate_token_batch(parts))
                else:
                    translated_active[i] = active_texts[i]
            if safe_tokens:
                results = self._translator.translate_batch(
                    safe_tokens,
                    batch_type="tokens",
                    max_batch_size=self._max_batch_size,
                )
                for pos, result in zip(safe_idx, results):
                    tgt_tokens = result.hypotheses[0]
                    tgt_ids = tok.convert_tokens_to_ids(tgt_tokens)
                    translated_active[pos] = tok.decode(tgt_ids, skip_special_tokens=True)
            chunk_out = list(chunk)
            for pos, translated in zip(active_idx, translated_active):
                chunk_out[pos] = translated if translated is not None else chunk[pos]
            out.extend(chunk_out)
        return out

    def translate_many(self, texts: list[str]) -> list[str]:
        """Dịch nhiều chuỗi; tự chia input dài > max_src_tokens rồi ghép lại (không cắt mất nội dung)."""
        if not texts:
            return []
        cleaned = [t if (t or "").strip() else "" for t in texts]
        # Flatten long inputs into sub-segments, translate, then reassemble.
        flat: list[str] = []
        spans: list[tuple[int, int]] = []  # (start, count) in flat for each cleaned item
        for text in cleaned:
            if not text.strip():
                spans.append((-1, 0))
                continue
            parts = _split_text_under_token_limit(
                text, self._input_token_len, max_tokens=self._max_src_tokens
            )
            start = len(flat)
            flat.extend(self._model_input(part) for part in parts)
            spans.append((start, len(parts)))

        if not flat:
            return list(cleaned)

        translated_flat = self._translate_token_batch(flat)
        out: list[str] = []
        for text, (start, count) in zip(cleaned, spans):
            if count <= 0:
                out.append(text)
            elif count == 1:
                out.append(translated_flat[start])
            else:
                out.append("".join(translated_flat[start : start + count]))
        return out


def model_status(model_dir: str | Path | None = None) -> dict:
    path = Path(model_dir) if model_dir else resolve_model_dir()
    ready = (path / "model.bin").is_file()
    if ready:
        message = f"Model OPUS-MT INT8 sẵn sàng: {path}"
    else:
        message = (
            f"Model CTranslate2 chưa có tại {path}. "
            "Cần tải model OPUS-MT en→vi INT8 trước khi dịch."
        )
    return {"ready": ready, "path": str(path), "message": message}


def get_translator(model_dir: Path | None = None) -> Ct2Translator:
    global _TRANSLATOR, _TRANSLATOR_DIR
    path = ensure_model(model_dir)
    with _TRANSLATOR_LOCK:
        if _TRANSLATOR is None or _TRANSLATOR_DIR != path:
            _TRANSLATOR = Ct2Translator(path)
            _TRANSLATOR_DIR = path
        return _TRANSLATOR


def reset_translator_cache() -> None:
    global _TRANSLATOR, _TRANSLATOR_DIR
    _TRANSLATOR = None
    _TRANSLATOR_DIR = None

__all__ = ['MtCt2Error', 'ModelNotReadyError', 'EmptyCsvError', 'TranslateCancelled', '_default_inter_threads', '_default_batch_size', '_flush_every_rows', '_fast_retry_default', '_split_text_under_token_limit', '_repo_root', 'resolve_model_dir', 'ensure_model', 'Ct2Translator', 'model_status', 'get_translator', 'reset_translator_cache']
