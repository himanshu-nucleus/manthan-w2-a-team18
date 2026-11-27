# L1 · Login

![Login](./L1-login.png)

| | |
|---|---|
| Role | All (unauthenticated) |
| Route (suggested) | /login |
| Figma node | 4020:4698 |
| Frame size | 1440 × 1024 |
| Sidebar variant | none |

## Purpose
Entry point for every role. The user signs in with work email and password; the left panel explains what ExpenseFlow does (live policy engine, multi-level approvals, payout batch).

## Layout
Two columns on a light lavender page background, no Sidebar or Topbar.
- **Brand panel** (left): 640 × 992, inset 16px from the page edges, large rounded corners (~24px), dark navy-to-purple gradient with two blurred glow ellipses (560px, 360px) and a few tiny white "star" dots.
- **Form area** (right): 784 × 992; the **Login card** (440 × 264, no visible card border/background) is centred vertically and horizontally.

## Content & components

### Brand panel (top to bottom, 48px left padding, content width 544)
- Logo row: 36 × 36 rounded square (purple-to-blue gradient) with a white receipt icon (ph/receipt), then wordmark **ExpenseFlow** (white, semibold).
- Large empty space (gradient only).
- Pill badge (240 × 34, translucent white border): icon `ph/sparkle-fill` + "Policy-driven expense claims".
- Headline, two lines, ~48px:
  - "Claims in minutes." (white)
  - "Approvals in hours." (light lavender/violet tint)
- Body text (white ~80% opacity): "Every line is checked against policy as you type. Duplicates are caught before payout, and every action is written to an append-only audit trail."
- Three feature rows (each 544 × 70, translucent card, 12px gap; 40px icon tile on the left, title + subtitle):

| Icon | Title | Subtitle |
|---|---|---|
| ph/shield-check | Live policy engine | Auto-approve, route or auto-reject with a reason |
| ph/tree-structure (flow) | Multi-level approvals | Manager → auditor above ₹25,000 → finance head above ₹1,00,000 |
| ph/bank | One-click payout batch | Bank-ready CSV, then claims move to Paid |

- Footer (small, muted white): "© 2026 ExpenseFlow · NucleusTeq"

### Login card (440 wide)
- Heading: **Sign in to your account** — ~32px, gradient text (purple #7c3aed → blue).
- Field 1: label "Work email"; text Input (440 × 36). Sample value `ananya.sharma@company.com`.
- Field 2: label "Password"; password Input (440 × 36), masked value shown.
- Button: **Sign in** — primary, full width (440 × 36), purple fill, white text, no icon.

No "forgot password", "remember me" or SSO link is shown.

## Interactions & states
- Behaviour (inferred): **Sign in** submits the form; on success the user lands on the dashboard for their role (employee → E1; manager → M1; auditor → A0; finance head → F0).
- Behaviour (inferred): Enter key in either field submits.
- Behaviour (inferred): Button shows a loading/disabled state while the request is in flight.
- Error state (not designed): on 401 show an inline error under the Password field or above the button, e.g. "Email or password is incorrect." Keep the email value; clear the password.
- Validation (inferred): both fields required; email field `type="email"`, `autocomplete="username"`; password `autocomplete="current-password"`.

## Data & API
- `POST /api/v1/auth/login` with `{"username", "password"}` → `access_token` (8-hour lifetime). Store the token and send `Authorization: Bearer <token>` on every call.
- **Gap:** the design asks for a **work email**, but the API takes a `username` (seed logins are `employee`, `manager`, `auditor`, `admin`, …). Either the backend accepts email as username, or the label changes. Team decision needed.
- Role for post-login redirect: Not yet in API in the login response as documented — needs either a `role` in the token response or a `/users/me` call (confirm with backend).

## Build notes
- shadcn: `Card` (optional, card has no visible chrome), `Label`, `Input`, `Button`, `Form` (react-hook-form + zod) for validation, `Alert` for the error.
- Brand panel is a pure presentational component (`AuthBrandPanel`); gradient + glows via Tailwind `bg-gradient-to-*` and absolutely positioned blurred circles (`blur-3xl`).
- Heading gradient text: `bg-gradient-to-r from-[#7c3aed] to-blue-600 bg-clip-text text-transparent`.
- Responsive (not designed): hide the brand panel below `lg` and centre the form.
- The ₹ thresholds in the feature row are marketing copy here, but policy limits are seeded config — do not reuse these strings as business logic.
