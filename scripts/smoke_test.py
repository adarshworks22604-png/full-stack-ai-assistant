"""Manual end-to-end check of a RUNNING backend (separate from the automated tests).

  1. Start the server:   uvicorn app.main:get_app --factory --port 8000   (from backend/)
  2. In another terminal (from backend/, venv active):   python ../scripts/smoke_test.py

Uses DEV_JWT_SECRET from backend/.env to mint a short-lived dev token. Synthetic data only.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import jwt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_dev_token import load_secret  # noqa: E402  (same folder as this script)


def token(user: str, products: list[str]) -> str:
    now = int(time.time())
    claims = {
        "sub": user,
        "iss": "outlook-assistant-dev",
        "aud": "outlook-assistant-api",
        "iat": now,
        "exp": now + 600,
        "products": products,
    }
    return jwt.encode(claims, load_secret(), algorithm="HS256")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    ok = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name} {detail}")

    with httpx.Client(base_url=args.base, timeout=30) as c:
        alice = {"Authorization": f"Bearer {token('alice', ['payments', 'web-portal'])}"}
        r = c.get("/health/live")
        check("health/live", r.status_code == 200 and r.json() == {"status": "ok"})
        r = c.get("/health/ready")
        check("health/ready", r.status_code == 200 and r.json() == {"status": "ready"})

        r = c.post("/api/v1/chat", json={"message": "hi"})
        check("no token -> 401", r.status_code == 401, r.json()["error"]["code"])

        r = c.post("/api/v1/chat", headers=alice, json={"message": ""})
        check("empty message -> 422", r.status_code == 422, r.json()["error"]["code"])

        body = {"message": "What is the fix?", "email_context": {"subject": "Payment error BUG-4821", "body_text": ""}}
        r = c.post("/api/v1/chat", headers=alice, json=body)
        answer = r.json().get("answer", "")
        check(
            "chat (JSON) known bug",
            r.status_code == 200 and "connection pool" in answer,
            f"request {r.headers['x-request-id']}",
        )

        events = []
        with c.stream("POST", "/api/v1/chat/stream", headers=alice, json=body) as s:
            stream_id = s.headers["x-request-id"]
            check("stream content-type", s.headers["content-type"].startswith("text/event-stream"))
            name = None
            for line in s.iter_lines():
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: ") and name:
                    events.append((name, json.loads(line[6:])))
        kinds = [e[0] for e in events]
        check(
            "stream order",
            kinds[0] == "request.started" and kinds[-1] == "request.done" and "assistant.final" in kinds,
            " > ".join(dict.fromkeys(kinds)),
        )

        r = c.get(f"/api/v1/requests/{stream_id}", headers=alice)
        check("request status", r.status_code == 200 and r.json()["status"] == "complete")
        r = c.post("/api/v1/feedback", headers=alice, json={"request_id": stream_id, "rating": "up"})
        check("feedback", r.status_code == 200)

        mallory = {"Authorization": f"Bearer {token('mallory', ['payments'])}"}
        r = c.get(f"/api/v1/requests/{stream_id}", headers=mallory)
        check("other user cannot see request", r.status_code == 404)

        r = c.post(
            "/api/v1/chat",
            headers=mallory,
            json={"message": "x", "email_context": {"subject": "BUG-7000", "body_text": ""}},
        )
        check("billing bug hidden without access", r.status_code == 200 and r.json()["sources"] == [])

    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
