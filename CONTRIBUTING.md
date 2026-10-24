# Contributing

- Branch from `main`: `feat/…`, `fix/…`, `docs/…`. Keep branches short-lived.
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- Open a PR, keep scope small, and make sure CI is green.
- Never commit secrets, real emails, proprietary bug records or internal docs. Use synthetic fixtures only.
- Record architectural decisions as short ADRs in `docs/decisions/` (context, options, decision, consequences).

## PR checklist
- [ ] Matches a documented requirement; limited in scope
- [ ] Tests added/updated; frontend and backend checks pass locally
- [ ] API contract and docs updated if behavior changed
- [ ] No secrets, private data, internal URLs or sensitive screenshots
- [ ] Auth, authorization, prompt-injection and failure paths considered
- [ ] Logs redacted; timeouts and retries bounded
- [ ] Reviewer can run the feature from documented steps
