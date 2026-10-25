"""Create a short-lived dev JWT for local testing. Never works against AUTH_MODE=entra.

Usage (from backend/, with DEV_JWT_SECRET set in the environment or .env):
  python ../scripts/make_dev_token.py --user alice --products payments web-portal
  python ../scripts/make_dev_token.py --user admin --products '*'
"""

import argparse
import os
import time
from pathlib import Path

import jwt


def load_secret() -> str:
    secret = os.environ.get("DEV_JWT_SECRET")
    if not secret and Path(".env").exists():
        for line in Path(".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("DEV_JWT_SECRET="):
                secret = line.split("=", 1)[1].strip()
    if not secret or len(secret) < 32:
        raise SystemExit("Set DEV_JWT_SECRET (32+ characters) in the environment or backend/.env")
    return secret


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="dev-user")
    parser.add_argument("--products", nargs="*", default=["payments", "web-portal"])
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()
    now = int(time.time())
    claims = {
        "sub": args.user,
        "iss": "outlook-assistant-dev",
        "aud": "outlook-assistant-api",
        "iat": now,
        "exp": now + args.minutes * 60,
        "products": args.products,
    }
    print(jwt.encode(claims, load_secret(), algorithm="HS256"))


if __name__ == "__main__":
    main()
