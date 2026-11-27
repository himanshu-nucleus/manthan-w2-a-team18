# ADR-003: Login identity and browser session

- **Status:** Accepted
- **Date:** 2026-11-27
- **Deciders:** Abhayraj (frontend), Himanshu (backend lead), Diksha (backend 2, DevOps/SRE), Rahul (UI/UX, QA)
- **Code:** `backend/app/api/auth.py`, `backend/app/security.py`, `backend/app/config.py`, `frontend/src/features/auth/token-storage.ts`, `frontend/src/features/auth/session.ts`, `frontend/src/lib/api.ts`

## Context

The login design (L1) asks for a work email and password. The backend's `POST /auth/login` took a `username` field and originally matched it against `users.username` only, so seeded users typing their email could not sign in (defect D3). The API returns a signed bearer token, not a cookie. ExpenseFlow is an internal tool: there is no public signup, and users are created by the finance head.

## Decision

1. **Identity.** The login form label is "Work email"; the value is sent as `username`. The backend matches it against username **or** email, trimmed and case-insensitive (`username == x OR lower(email) == x`). Unknown user, wrong password and inactive user all return the same `401`, and each failure writes a `LOGIN_FAILED` audit row (never the password). Covered by 3 backend tests.
2. **Token.** `POST /auth/login` returns a signed, timed token (`itsdangerous` serializer) that expires after 8 hours (`access_token_ttl_seconds = 8 * 60 * 60`). The SPA sends it as `Authorization: Bearer …`.
3. **Storage.** The token is kept in `localStorage` (`expenseflow.access_token`) so a reload or new tab keeps the user signed in. Every storage access is wrapped in try/catch (private mode or blocked storage behaves as "signed out"). Any `401` while a token is stored clears it, and the `_authed` layout then redirects to `/login`. Sign out clears it.
4. **No signup.** The finance head creates users on `/admin/people` (`POST /users`, audited as `USER_CREATED`). Usernames may contain `@` and `+` so an email can be used as the username (defect D2 fix).

## Alternatives considered

| Option | Why not (for now) |
| --- | --- |
| httpOnly `Secure` `SameSite` cookie session | Best protection against token theft by XSS. Needs backend changes (set-cookie on login, cookie auth dependency, CSRF protection for POST/PUT/DELETE) that did not fit the hackathon time. The same-origin nginx proxy already makes this possible later without CORS work. |
| `sessionStorage` | Same XSS exposure as `localStorage`, and the user is signed out in every new tab, which hurts approvers opening claims from the queue. |
| In-memory only | Not readable by injected scripts after the fact, but every reload signs the user out; would need a refresh-token cookie to be usable, which is the cookie option again. |
| Separate email field in the API | Would change the contract for every client; accepting either value in `username` kept `openapi.json` compatible. |

## Consequences

- **XSS is the main risk.** Any script running on the page can read the token and use it until it expires (up to 8 hours). Mitigations in place: React escapes output by default, `frontend/src` contains no `dangerouslySetInnerHTML`, dependencies pass `pnpm audit --prod` with no known vulnerabilities. Not in place: a Content-Security-Policy header in `nginx.conf`, server-side token revocation (logout only deletes the local copy).
- A user stays signed in across reloads and tabs for up to 8 hours; an expired token is cleaned up on the first `401`.
- One `401` for every login failure means the form cannot reveal whether an account exists.
- No rate limit on login yet; failed attempts are visible as `LOGIN_FAILED` rows in the audit trail.
- Account lifecycle is entirely in the finance head's hands; there is no self-service password reset.
