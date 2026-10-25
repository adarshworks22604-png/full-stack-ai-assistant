import json
import logging

from app.core.context import request_id_var
from app.core.logging import JsonFormatter, RedactingFilter, redact


def test_redacts_bearer_tokens_jwts_and_key_assignments():
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
    out = redact(f"Authorization: Bearer abc.def-123 token={jwt_like} api_key=sk-12345 password: hunter2")
    for secret in ("abc.def-123", jwt_like, "sk-12345", "hunter2"):
        assert secret not in out


def test_json_logs_carry_the_request_id_and_redact_secrets():
    record_holder = []

    class Capture(logging.Handler):
        def emit(self, record):
            record_holder.append(self.format(record))

    handler = Capture()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.redaction")
    logger.handlers, logger.propagate = [handler], False
    logger.setLevel(logging.INFO)

    token = request_id_var.set("req_abc")
    try:
        logger.info("calling upstream with Bearer SECRETTOKEN123")
        try:
            raise RuntimeError("failed with api_key=sk-LEAK")
        except RuntimeError:
            logger.exception("boom")
    finally:
        request_id_var.reset(token)

    first, second = (json.loads(x) for x in record_holder)
    assert first["request_id"] == "req_abc"
    assert "SECRETTOKEN123" not in record_holder[0]
    assert "sk-LEAK" not in record_holder[1] and "exc" in second
