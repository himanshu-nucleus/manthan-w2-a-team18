# ExpenseFlow UI design

Screens exported from Figma for the frontend build (React 19 + Vite + shadcn/ui).

- **Figma:** [ExpenseFlow · UI](https://www.figma.com/design/1XAnGEKVeQflpveXADQ7MX/shadcn-ui-kit-community-edition--Community-?node-id=4006-2) (page node `4006:2`)
- **Exported:** 2026-11-27 (re-exported after the design update). Desktop PNGs are 1× (1440px wide); mobile PNGs are 2× (780px wide = 390pt)
- **Start here:** [foundations.md](./foundations.md) covers colour tokens, type, spacing, the shared
  Sidebar/Topbar layout, components and icons. Build those first, because every screen reuses them.

Each screen has a PNG and a Markdown spec in [screens/](./screens/) with the same name. The spec
covers purpose, layout, every element and its copy, interactions, the data and API it needs, and build notes.

## Screen index

### Authentication

| ID | Screen | Spec |
|---|---|---|
| L1 | Login | [L1-login.md](./screens/L1-login.md) |

### Employee

| ID | Screen | Spec |
|---|---|---|
| E1 | Employee dashboard | [E1-employee-dashboard.md](./screens/E1-employee-dashboard.md) |
| E2 | My claims | [E2-my-claims.md](./screens/E2-my-claims.md) |
| E3 | Draft with expenses (lines, receipts, live policy) | [E3-draft-with-expenses.md](./screens/E3-draft-with-expenses.md) |
| E4 | Review & submit | [E4-review-and-submit.md](./screens/E4-review-and-submit.md) |
| E5 | Claim detail, timeline & clarification | [E5-claim-detail-timeline.md](./screens/E5-claim-detail-timeline.md) |

### New claim flow (employee)

| ID | Screen | Spec |
|---|---|---|
| N1 | Step 1: Start a new claim | [N1-start-new-claim.md](./screens/N1-start-new-claim.md) |
| N2 | Step 2: Empty draft, add the first expense | [N2-empty-draft.md](./screens/N2-empty-draft.md) |
| N3 | Step 3: Add an expense (sheet) | [N3-add-expense-sheet.md](./screens/N3-add-expense-sheet.md) |
| N4 | Step 4 done: Claim submitted (Figma label "N6") | [N4-claim-submitted.md](./screens/N4-claim-submitted.md) |

### Line manager

| ID | Screen | Spec |
|---|---|---|
| M1 | Manager dashboard | [M1-manager-dashboard.md](./screens/M1-manager-dashboard.md) |
| M2 | Approvals queue (bulk approve) | [M2-approvals-queue.md](./screens/M2-approvals-queue.md) |
| M3 | Review a claim (approve / reject / send back) | [M3-review-claim.md](./screens/M3-review-claim.md) |
| M4 | Out of office & delegation | [M4-out-of-office-delegation.md](./screens/M4-out-of-office-delegation.md) |

### Finance auditor

| ID | Screen | Spec |
|---|---|---|
| A0 | Auditor dashboard | [A0-auditor-dashboard.md](./screens/A0-auditor-dashboard.md) |
| A1 | Audit queue (filters, bulk approve, 10% sample) | [A1-audit-queue.md](./screens/A1-audit-queue.md) |
| A2 | Audit a claim (duplicate detection) | [A2-audit-claim-duplicates.md](./screens/A2-audit-claim-duplicates.md) |
| A3 | Audit history | [A3-audit-history.md](./screens/A3-audit-history.md) |

### Finance head / admin

| ID | Screen | Spec |
|---|---|---|
| F0 | Finance head dashboard (now includes spend by category and by department) | [F0-finance-head-dashboard.md](./screens/F0-finance-head-dashboard.md) |
| F2 | Payout batches & CSV export | [F2-payout-batches-csv.md](./screens/F2-payout-batches-csv.md) |
| F3 | Policy rules (configuration) | [F3-policy-rules.md](./screens/F3-policy-rules.md) |
| F4 | Approval chain & people | [F4-approval-chain-people.md](./screens/F4-approval-chain-people.md) |
| F5 | Audit trail (append-only) | [F5-audit-trail.md](./screens/F5-audit-trail.md) |

The separate **F1 Spend analytics** screen was removed from Figma. Its charts are now on F0. The
Finance head sidebar still shows a "Spend analytics" item, so ask design whether to drop it or point it at F0.

### Mobile: employee claim capture (390 × 844)

| ID | Screen | Spec |
|---|---|---|
| MB1 | Home | [MB1-home.md](./screens/MB1-home.md) |
| MB2 | Scan receipt | [MB2-scan-receipt.md](./screens/MB2-scan-receipt.md) |
| MB3 | Check details (read from receipt) | [MB3-check-details.md](./screens/MB3-check-details.md) |
| MB4 | Add expense (manual, hotel) | [MB4-add-expense-manual.md](./screens/MB4-add-expense-manual.md) |
| MB5 | Policy result states | [MB5-policy-result-states.md](./screens/MB5-policy-result-states.md) |
| MB6 | Draft claim | [MB6-draft-claim.md](./screens/MB6-draft-claim.md) |
| MB7 | Review & submit | [MB7-review-and-submit.md](./screens/MB7-review-and-submit.md) |
| MB8 | Claim status (sent back) | [MB8-claim-status-sent-back.md](./screens/MB8-claim-status-sent-back.md) |
| MB9 | Mobile states | [MB9-mobile-states.md](./screens/MB9-mobile-states.md) |

## Main flow

```
L1 Login ─▶ role dashboard (E1 / M1 / A0 / F0)

Employee:  E1 ─▶ N1 start ─▶ N2 empty draft ─▶ N3 add expense (sheet) ─▶ E3 draft ─▶ E4 review ─▶ N4 submitted
           E1 / E2 ─▶ E5 claim detail (timeline, answer clarification)
Mobile:    MB1 home ─▶ MB2 scan ─▶ MB3 check details ─▶ MB5 policy result ─▶ MB6 draft ─▶ MB7 review & submit
           MB1 ─▶ MB4 add manually;  MB1 ─▶ MB8 claim status (sent back);  MB9 = offline/empty/loading states
Manager:   M1 ─▶ M2 queue ─▶ M3 review ─▶ approve │ reject │ send back (─▶ employee E5)
Auditor:   A0 ─▶ A1 queue ─▶ A2 audit (duplicates) ─▶ approve for payout │ return
Finance:   F0 (incl. spend analytics) ─▶ F2 payout batch ─▶ CSV export;  F3 policy rules, F4 approval chain, F5 audit trail
```

Claim lifecycle shown in the designs: Draft → Submitted → Manager approved → Audited → In payout batch → Paid,
with side paths Sent back (needs clarification) and Rejected. The backend currently implements
`DRAFT` and `SUBMITTED` only (see [../claims-api.md](../claims-api.md)). Each spec's "Data & API" section
marks what is not yet in the API.

## Suggested build order

1. Foundations: tokens in `index.css`, Geist font, the `StatusChip`, `KpiCard`, `Sidebar` (role-driven config), `Topbar` and `AppShell` components.
2. L1 Login, then the employee path E1 → N1–N4 → E3/E4 → E2 → E5. This is the demo's core journey.
3. Manager M2/M3, then auditor A1/A2, then finance F2.
4. The dashboards (M1, A0, F0) and configuration screens (F3, F4, F5, M4).
5. Mobile (MB1–MB9): make the employee screens responsive below 640px. They are the same claim flow as N1–N4/E3–E5 with a bottom tab bar instead of the sidebar.

## Folder layout

```
docs/design/
  README.md              this index
  foundations.md         tokens, layout, components, icons
  components/
    components-sheet.png Figma "ExpenseFlow Components" frame
  screens/
    <ID>-<name>.png      export of each Figma frame (desktop 1×, mobile 2×)
    <ID>-<name>.md       screen spec
```

To refresh a PNG after a design change, re-export the frame from Figma (desktop at 1×, mobile at 2×)
or ask Claude to re-export it with the Figma MCP, using the node IDs given in each spec. The Figma
page also has an older dark-panel login (`4026:4734`, in a duplicate "Authentication" section). It is
superseded by L1 (`4028:4754`) and is not exported.
