# ADR 0002: Pluggable token verification
**Context:** The add-in must authenticate users to our API, but Entra ID app registration is not available for local work.
**Options:** (a) skip auth locally; (b) one verifier per environment behind an interface.
**Decision:** `TokenVerifier` interface. `DevJwtVerifier` (HS256, local secret) for development; `EntraJwtVerifier`
(RS256, JWKS) for production. Config validation refuses dev auth unless `APP_ENV=local`, so it cannot ship by accident.
Authorization (product access) is separate from authentication and enforced in code, never by the LLM.
**Consequences:** All routes are protected from day one and tests use real signed tokens. The Entra verifier is tested
against a locally generated RSA key, **not** live Entra: token version (v1/v2 issuer), audience, and the group-to-product
mapping must be confirmed against the real tenant and the Office add-in SSO flow before production (Stage 9).
