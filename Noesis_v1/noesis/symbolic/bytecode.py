"""Bytecode encoding — compact binary serialization of symbolic memory."""

from __future__ import annotations

import zlib
from typing import Any

import msgpack


class BytecodeEncoder:
    """Converts token IDs + metadata into compressed portable bytecode."""

    def encode(self, payload: dict[str, Any], use_zlib: bool = False) -> bytes:
        packed = msgpack.packb(payload, use_bin_type=True)
        if use_zlib:
            return zlib.compress(packed, level=9)
        return packed

    def decode(self, bytecode: bytes, use_zlib: bool = False) -> dict[str, Any]:
        data = bytecode
        if use_zlib:
            data = zlib.decompress(bytecode)
        return msgpack.unpackb(data, raw=False)
