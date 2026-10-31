"""CLI: print a PBKDF2 hash for ADMIN_PASSWORD_HASH.

Usage:
    python -m server.hash_password 'S3cretPassword!'
"""

from __future__ import annotations

import sys

from server.auth import hash_password


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m server.hash_password 'PASSWORD'", file=sys.stderr)
        raise SystemExit(2)
    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    main()
