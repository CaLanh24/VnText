"""Bounded reader for Ren'Py RPA 3.0 archives without pickle execution."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pickletools
import re
from urllib.parse import parse_qs, quote, unquote, urlsplit
import zlib

MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 200_000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
_HEADER = re.compile(rb"RPA-3\.0 ([0-9a-fA-F]{16}) ([0-9a-fA-F]{8})\n\Z")
_HEADER2 = re.compile(rb"RPA-2\.0 ([0-9a-fA-F]{8,16})\n\Z")


class RenPyArchiveError(ValueError):
    pass


def resolved_game_path(member: str) -> str:
    """Resolve a raw member relative to game/, retaining legacy game/ roots."""
    if not RenPyArchive._safe_name(member):
        raise RenPyArchiveError("unsafe RPA member path")
    parts=member.split('/')
    return 'game/'+ '/'.join(parts[1:])if parts[0].casefold()=='game'else 'game/'+member


def member_reference(container: str | Path, member: str) -> str:
    path = Path(container).resolve()
    if not RenPyArchive._safe_name(member):
        raise RenPyArchiveError("unsafe RPA member path")
    return f"rpa-member://{quote(str(path), safe='')}?member={quote(member, safe='')}"


def parse_member_reference(value: str) -> tuple[Path, str] | None:
    if not value.startswith("rpa-member://"):
        return None
    parts = urlsplit(value)
    query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if parts.scheme != "rpa-member" or not parts.netloc or parts.path or parts.fragment or set(query) != {"member"} or len(query["member"]) != 1:
        raise RenPyArchiveError("malformed RPA member reference")
    return Path(unquote(parts.netloc)).resolve(), query["member"][0]


def _safe_index(data: bytes) -> dict:
    """Interpret only primitive container/index opcodes emitted by Ren'Py."""
    stack: list[object] = []
    memo: dict[int, object] = {}
    next_memo = 0
    marks: list[int] = []
    last_end = 0
    try:
        for op, arg, pos in pickletools.genops(data):
            last_end = pos + 1
            name = op.name
            if name in {"PROTO", "FRAME"}:
                continue
            if name == "STOP":
                break
            if name == "MARK":
                marks.append(len(stack)); continue
            if name in {"BININT", "BININT1", "BININT2", "LONG1", "LONG4", "INT", "LONG"}:
                if type(arg) is not int: raise RenPyArchiveError("RPA index integer is malformed")
                stack.append(arg); continue
            if name in {"SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "UNICODE"}:
                if not isinstance(arg, str): raise RenPyArchiveError("RPA index path is malformed")
                stack.append(arg); continue
            if name in {"SHORT_BINBYTES", "BINBYTES", "BINBYTES8", "BYTEARRAY8"}:
                if not isinstance(arg, (bytes, bytearray)): raise RenPyArchiveError("RPA index bytes are malformed")
                stack.append(bytes(arg)); continue
            if name == "NONE": stack.append(None); continue
            if name == "EMPTY_DICT": stack.append({}); continue
            if name == "EMPTY_LIST": stack.append([]); continue
            if name in {"TUPLE2", "TUPLE3"}:
                count = 2 if name == "TUPLE2" else 3
                if len(stack) < count: raise RenPyArchiveError("RPA index stack underflow")
                values = stack[-count:]; del stack[-count:]; stack.append(tuple(values)); continue
            if name == "TUPLE":
                if not marks: raise RenPyArchiveError("RPA index tuple mark missing")
                mark = marks.pop(); values = stack[mark:]; del stack[mark:]; stack.append(tuple(values)); continue
            if name in {"APPEND", "APPENDS"}:
                if name == "APPEND":
                    if len(stack) < 2 or not isinstance(stack[-2], list): raise RenPyArchiveError("RPA index list malformed")
                    stack[-2].append(stack.pop())
                else:
                    if not marks or not stack: raise RenPyArchiveError("RPA index list mark missing")
                    mark = marks.pop(); values = stack[mark:]; del stack[mark:]
                    target = stack[-1]
                    if not isinstance(target, list): raise RenPyArchiveError("RPA index list malformed")
                    target.extend(values)
                continue
            if name in {"SETITEM", "SETITEMS"}:
                if name == "SETITEM":
                    if len(stack) < 3 or not isinstance(stack[-3], dict): raise RenPyArchiveError("RPA index mapping malformed")
                    value = stack.pop(); key = stack.pop(); target = stack[-1]
                    if key in target: raise RenPyArchiveError("RPA archive contains duplicate member path")
                    target[key] = value
                else:
                    if not marks or not stack: raise RenPyArchiveError("RPA index mapping mark missing")
                    mark = marks.pop(); values = stack[mark:]; del stack[mark:]
                    target = stack[-1]
                    if not isinstance(target, dict) or len(values) % 2: raise RenPyArchiveError("RPA index mapping malformed")
                    for i in range(0, len(values), 2):
                        if values[i] in target: raise RenPyArchiveError("RPA archive contains duplicate member path")
                        target[values[i]] = values[i + 1]
                continue
            if name == "MEMOIZE": memo[next_memo] = stack[-1]; next_memo += 1; continue
            if name in {"BINPUT", "LONG_BINPUT", "PUT"}: memo[int(arg)] = stack[-1]; continue
            if name in {"BINGET", "LONG_BINGET", "GET"}: stack.append(memo[int(arg)]); continue
            raise RenPyArchiveError(f"unsupported RPA index opcode: {name}")
    except (ValueError, IndexError, KeyError, TypeError) as exc:
        if isinstance(exc, RenPyArchiveError): raise
        raise RenPyArchiveError(f"invalid RPA index: {exc}") from exc
    if last_end != len(data) or marks or len(stack) != 1 or not isinstance(stack[0], dict):
        raise RenPyArchiveError("RPA index has trailing data or invalid root")
    return stack[0]


class RenPyArchive:
    def __init__(self, path: str | Path):
        candidate = Path(path).absolute()
        for part in (candidate, *candidate.parents):
            if part.exists() and (part.is_symlink() or getattr(part.stat(), "st_file_attributes", 0) & 0x400):
                raise RenPyArchiveError("RPA archive path must not pass through a link or reparse point")
        self.path = candidate.resolve()
        info = self.path.lstat()
        if not self.path.is_file() or os.path.islink(self.path) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RenPyArchiveError("RPA archive must be a regular file")
        self.size = info.st_size
        self.container_sha256 = self._hash_file()
        with self.path.open("rb") as f:
            header = f.readline(128)
            match = _HEADER.fullmatch(header)
            match2 = _HEADER2.fullmatch(header) if not match else None
            if not match and not match2: raise RenPyArchiveError("unsupported RPA format; supported formats are RPA-2.0 and RPA-3.0")
            self.version = "3.0" if match else "2.0"
            self.index_offset = int((match or match2).group(1), 16); key = int(match.group(2), 16) if match else 0
            if self.index_offset < len(header) or self.index_offset >= self.size:
                raise RenPyArchiveError("RPA index offset is outside archive")
            f.seek(self.index_offset); compressed = f.read(MAX_INDEX_BYTES + 1)
        if len(compressed) > MAX_INDEX_BYTES: raise RenPyArchiveError("RPA compressed index exceeds 64 MiB")
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, MAX_INDEX_BYTES + 1)
        if len(raw) > MAX_INDEX_BYTES or inflater.unconsumed_tail or not inflater.eof or inflater.unused_data:
            raise RenPyArchiveError("RPA index is oversized, truncated, or has trailing data")
        index = _safe_index(raw)
        if len(index) > MAX_MEMBERS: raise RenPyArchiveError("RPA member count exceeds limit")
        self.members: dict[str, tuple[tuple[int, int, bytes], ...]] = {}
        all_ranges: list[tuple[int, int]] = []
        folded_names: set[str] = set()
        for raw_name, raw_chunks in index.items():
            if not isinstance(raw_name, str) or not self._safe_name(raw_name) or not isinstance(raw_chunks, list) or not raw_chunks:
                raise RenPyArchiveError("RPA member path or chunk list is invalid")
            folded = raw_name.casefold()
            if folded in folded_names: raise RenPyArchiveError("RPA member paths collide case-insensitively")
            folded_names.add(folded)
            chunks = []
            for chunk in raw_chunks:
                if not isinstance(chunk, tuple) or len(chunk) not in {2, 3}:
                    raise RenPyArchiveError("RPA member chunk is malformed")
                offset, length = chunk[:2]
                prefix = chunk[2] if len(chunk) == 3 else b""
                if type(offset) is not int or type(length) is not int or not isinstance(prefix, (bytes, str)):
                    raise RenPyArchiveError("RPA member chunk fields are invalid")
                if isinstance(prefix, str): prefix = prefix.encode("latin-1")
                if match: offset ^= key; length ^= key
                if offset < len(header) or length < 0 or offset + length > self.index_offset or length + len(prefix) > MAX_MEMBER_BYTES:
                    raise RenPyArchiveError("RPA member range is outside data area or exceeds 64 MiB")
                chunks.append((offset, length, prefix)); all_ranges.append((offset, offset + length))
            self.members[raw_name] = tuple(chunks)
        ordered = sorted(all_ranges)
        if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
            raise RenPyArchiveError("RPA member ranges overlap")
        if self._hash_file() != self.container_sha256:
            raise RenPyArchiveError("RPA archive changed while its index was being read")

    @staticmethod
    def _safe_name(name: str) -> bool:
        parts = name.split("/")
        reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
        invalid = set('<>:"|?*')
        return bool(name) and "\\" not in name and all(
            part not in {"", ".", ".."} and not any(ord(ch) < 32 or ch in invalid for ch in part)
            and not part.endswith((".", " ")) and part.split(".", 1)[0].casefold() not in reserved
            for part in parts
        )

    def _hash_file(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""): digest.update(block)
        return digest.hexdigest()

    def read_member(self, name: str) -> dict:
        try: chunks = self.members[name]
        except KeyError as exc: raise RenPyArchiveError(f"archive member not found: {name}") from exc
        if sum(length + len(prefix) for _offset, length, prefix in chunks) > MAX_MEMBER_BYTES:
            raise RenPyArchiveError("RPA member exceeds 64 MiB")
        parts = []
        with self.path.open("rb") as f:
            for offset, length, prefix in chunks:
                f.seek(offset); data = f.read(length)
                if len(data) != length: raise RenPyArchiveError("RPA member changed or truncated during read")
                parts.append(prefix + data)
        content = b"".join(parts)
        if self._hash_file() != self.container_sha256:
            raise RenPyArchiveError("RPA archive changed while its member was being read")
        if len(content) > MAX_MEMBER_BYTES: raise RenPyArchiveError("RPA member exceeds 64 MiB")
        return {"name": name, "container_path": str(self.path), "container_sha256": self.container_sha256,
                "member_sha256": hashlib.sha256(content).hexdigest(), "content": content}

    def member_size(self, name: str) -> int:
        try: chunks = self.members[name]
        except KeyError as exc: raise RenPyArchiveError(f"archive member not found: {name}") from exc
        size = sum(length + len(prefix) for _offset, length, prefix in chunks)
        if size > MAX_MEMBER_BYTES: raise RenPyArchiveError("RPA member exceeds 64 MiB")
        return size
