"""Shared token-counting helper. Provider-agnostic proxy (cl100k_base) since the embedding
model is not finalized yet — swap the encoding here once it is, without touching callers."""
from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))
