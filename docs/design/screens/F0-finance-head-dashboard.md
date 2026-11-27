# F0 · Finance head dashboard

![Finance head dashboard](./F0-finance-head-dashboard.png)

| | |
|---|---|
| Role | Finance head |
| Route (suggested) | /finance |
| Figma node | 4017:3392 |
| Frame size | 1440 × 1233 |
| Sidebar variant | Finance head (active item: Dashboard) |

## Purpose
Landing page for the finance head (Rajesh Menon). It shows the month's company-wide spend, what is ready for payout,
the items that need their action (payout batch, high-value approvals, unpublished policy draft) and recent finance events.

## Layout
1. Topbar (shared; Context dropdown reads "Company-wide").
2. Greeting header row (1116 × 90): greeting block left, two buttons right.
3. "Finance overview" card (1116 × 387): title row with month Select and kebab, 5 KPI Cards in one row, two AI insight lines, AI prompt bar. Soft purple gradient blobs top-right.
4. Two-column row (1116 × 299): "Needs your action" card (596 wide) left, "Monthly spend" chart card (500 wide) right.
5. "Recent finance events" card (1116 × 253): header + 4-column table.

## Content & components

### Greeting header
- Small text: "Hi Rajesh Menon"
- Headline (large, primary purple gradient): "₹42.7 L is ready for the November payout."
- Sub-text (muted, small): "Company-wide · 150 employees · 8 departments · November 2026"
- Buttons (right): "Spend analytics" — outline, icon ph/chart-line-up; "Create payout batch" — primary, icon ph/bank.

### Finance overview card
- Title "Finance overview" with round icon ph/list-checks; right side: Select "November" and a ghost icon button (ph/dots-three-vertical).
- KPI Cards (each with a tinted icon tile):

| Label | Icon | Value | Sub-text |
|---|---|---|---|
| Claims | ph/receipt | 1,284 | ↑ 4% vs Oct · 150 employees |
| Total spend | ph/wallet | ₹68.4 L | ↑ 6% vs October |
| Policy violations | ph/warning | 126 | 4.2% of all lines |
| Avg approval time | ph/clock | 19 h | Was 9.8 days in Excel |
| Ready for payout | ph/bank | ₹42.7 L | 186 approved claims |

- Insight lines (ph/sparkle icon, purple):
  - "2 claims over ₹1,00,000 are waiting for your approval." + link "Review"
  - "Cab limit breaches rose 18% — policy draft v7 proposes ₹2,500." + link "Open draft"
- AI prompt bar (pill, purple border): placeholder "Ask ExpenseFlow AI anything…", two dashed suggestion chips "Why did hotel spend rise?" (ph/bed) and "Draft the payout summary" (ph/file-csv), dark round send button with ph/sparkle.

### Needs your action card
- Title "Needs your action", count badge "3" (purple).
- Three action rows (bordered, icon tile left, action right):

| Icon | Title | Chip (tone) | Sub-text | Button |
|---|---|---|---|---|
| ph/bank | Create November payout batch | 186 claims (info) | 3 claims held: sample audit or bank details | Create batch (primary) |
| ph/list-checks (amber tile) | 2 claims over ₹1,00,000 | Your approval (warning) | Sales offsite ₹1,42,000 · Delivery onsite ₹1,08,500 | Review (outline) |
| ph/scales | Policy draft v7 not published | Draft (neutral, clock icon) | Cab limit ₹2,000 → ₹2,500 | Open (outline) |

### Monthly spend card
- Title "Monthly spend", sub-text "Jan – Dec 2026", chip "₹ lakh" (neutral, clock icon).
- Area chart: single purple series, gradient fill, x-axis Jan…Dec, no visible y-axis or gridlines; last point (Dec) has a hollow circle marker. Trend rises from ~Jan to Dec with small dips (Mar, Jun, Sep). Exact values not labelled.

### Recent finance events card
- Title "Recent finance events"; right link "Audit trail" (ghost).
- Table:

| Time | Actor | Event (chip, tone) | Details |
|---|---|---|---|
| 26 Nov 17:05 | Rajesh Menon (avatar) | Batch exported (purple) | NOV-2026-01 · ₹38.2 L · locked |
| 26 Nov 11:12 | Sana Iqbal (avatar) | Bulk approved (success) | 4 claims over ₹25,000 |
| 25 Nov 09:00 | System (dark sparkle avatar) | Sample audit drawn (info) | 14 of 141 auto-approved claims |

## Interactions & states
- "Spend analytics" → F1. "Create payout batch" / "Create batch" (row and Sidebar Promo Card) → F2 (Behaviour (inferred): creates a draft batch for the selected month, then opens it).
- "Review" (insight link and row button) → M2 approvals queue filtered to claims over ₹1,00,000 awaiting the finance head (inferred).
- "Open draft" / "Open" → F3 with draft v7.
- "Audit trail" → F5.
- Month Select re-scopes the KPIs and action list (inferred). Kebab menu contents not shown.
- AI prompt bar and suggestion chips: Behaviour (inferred): send the question to an assistant; response UI is not designed.
- KPI deltas: "↑" in muted text; no red/green colouring shown.
- Empty/loading states not designed; suggest skeleton KPI Cards and "Nothing needs your action" for an empty list.

## Data & API
- Greeting: current user name — `/users` (logged-in user).
- KPIs (claim count, total spend, violations, avg approval time, ready-for-payout amount/count) — Not yet in API: finance summary/dashboard endpoint.
- Insight lines and AI assistant — Not yet in API.
- Needs-action items (draft batch, claims awaiting finance-head approval, unpublished policy draft) — Not yet in API (approval states, payout batches, policy versions).
- Monthly spend series — Not yet in API.
- Recent finance events — Not yet in API: a global audit feed; only per-claim `GET /claims/{id}/audit` exists.

## Build notes
- shadcn: Card, Button, Select, DropdownMenu, Badge (Status Chip), Table, Avatar, Input (prompt bar), Chart (Recharts AreaChart).
- Reuse KPI Card (also on F1), Status Chip, the action-row component (similar rows likely on M1/A0 dashboards).
- Format money with Indian grouping and lakh abbreviation ("₹42.7 L") via one shared formatter.
- Headline uses a purple gradient text fill (bg-clip-text).
