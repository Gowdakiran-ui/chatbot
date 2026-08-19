"""Pre-launch client token issuance (Piece 1 of the security/auth hardening task).

Generates a random bearer token for a new client account and stores only its
SHA-256 hash (see serving/auth.py) — the raw token is printed exactly once here
and is not recoverable afterward. Give it directly to the client; if it's lost, an
operator issues a new one (this stage has no rotation/revocation UI yet, deliberately
— see serving/auth.py's docstring on not over-building the user service too early).

Usage:
    python -m scripts.issue_token <client_id> <label>
    python -m scripts.issue_token acme_corp "Acme Corp"
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root, for `serving.*`

from serving.auth import create_client


def issue_token(client_id: str, label: str) -> str:
    token = secrets.token_urlsafe(32)
    create_client(client_id, label, token)
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_id", help="Unique, stable identifier for this client account")
    parser.add_argument("label", help="Human-readable name, for logs/auditing")
    args = parser.parse_args()

    token = issue_token(args.client_id, args.label)
    print(f"Client '{args.client_id}' ({args.label}) created.")
    print("Token (shown once — store it securely, it cannot be recovered):")
    print(token)


if __name__ == "__main__":
    main()
