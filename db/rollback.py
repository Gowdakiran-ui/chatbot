"""Repoint a KB's alias back at an older version — nothing fancier.

Usage:
    python -m db.rollback chanakya_kb 1
    python -m db.rollback crisis_kb 2
"""
from __future__ import annotations

import argparse

from db.config import CHANAKYA_COLLECTION_BASE, CRISIS_COLLECTION_BASE
from db.versioning import collection_name, current_alias_target, flip_alias, list_versions


def _get_client_for(base: str):
    if base == CHANAKYA_COLLECTION_BASE:
        from db.qdrant_client import get_client

        return get_client()
    if base == CRISIS_COLLECTION_BASE:
        from db.crisis_qdrant_client import get_client

        return get_client()
    raise ValueError(f"Unknown KB base '{base}' — expected '{CHANAKYA_COLLECTION_BASE}' or '{CRISIS_COLLECTION_BASE}'")


def rollback(base: str, version: int) -> None:
    client = _get_client_for(base)
    target = collection_name(base, version)

    if not client.collection_exists(target):
        available = list_versions(client, base)
        raise RuntimeError(f"'{target}' doesn't exist. Available versions for '{base}': {available}")

    before = current_alias_target(client, base)
    flip_alias(client, base, target)
    print(f"'{base}': alias moved {before!r} -> {target!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kb", choices=[CHANAKYA_COLLECTION_BASE, CRISIS_COLLECTION_BASE])
    parser.add_argument("version", type=int, help="Version number to roll back to, e.g. 1")
    args = parser.parse_args()
    rollback(args.kb, args.version)


if __name__ == "__main__":
    main()
