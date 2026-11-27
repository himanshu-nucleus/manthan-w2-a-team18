# F3 · Policy rules (configuration)

![Policy rules](./F3-policy-rules.png)

| | |
|---|---|
| Role | Finance head (Admin) |
| Route (suggested) | /admin/policy |
| Figma node | 4018:4000 |
| Frame size | 1440 × 1024 |
| Sidebar variant | Finance head (active item: Policy rules) |

## Purpose
The finance head edits expense policy rules as versioned configuration (not code): limits per category, what happens
on a breach, and when a new version takes effect. Draft versions are published; history is kept and audited.

## Layout
1. Topbar (shared).
2. Page header (1116 × 47): eyebrow + title + chip left; two buttons right.
3. Draft banner (1116 × 78, light purple, bordered): icon, text, "Effective from" date input right.
4. Two-column row: rules table card (776 × 494) left, "Version history" card (320 × 324) right.

## Content & components

### Page header
- Eyebrow "Finance head · Admin"; title "Policy rules"; chip "Rules are configuration, not code" (purple, ph/sparkle).
- Buttons: "Discard draft" — outline, ph/trash; "Publish v7" — primary, ph/rocket-launch.

### Draft banner
- Icon tile ph/pencil-simple-line.
- Title "Editing draft v7"; text "Live version v6 since 01 Oct 2026. Claims are judged by the version live when they were submitted."
- Label "Effective from" + Input (date) value "01 Dec 2026".

### Rules table
Columns: Rule · Applies to · Limit (₹) (right-aligned) · Per · When breached (Select) · Status (chip).

| Rule (icon) | Applies to | Limit (₹) | Per | When breached | Status |
|---|---|---|---|---|---|
| Meals (ph/fork-knife) | All cities | 1,500 | day | Auto-reject excess | Live (success) |
| Hotel (ph/bed) | Tier-1 cities (8) | 6,000 | night | Route for approval | Live |
| Hotel (ph/bed) | Other cities | 4,000 | night | Route for approval | Live |
| Local cab (ph/car) | All cities | ~~2,000~~ **2,500** | trip | Route for approval | Changed (warning) |
| Receipt (ph/receipt) | All categories | 500 | line | Block submit | Live |
| Duplicate (ph/copy) | Vendor + amount + date, file hash | — | line | Route to auditor | Live |
| Weekend (ph/calendar) | Sat, Sun | — | line | Flag to manager | Live |
| Sample audit (ph/flag) | Auto-approved claims | 10% | claims | Hold for auditor | Live |

- Changed row ("Local cab") has a light purple row background; old value 2,000 shown muted, new value 2,500 in bold purple.
- "When breached" options visible in the design: Auto-reject excess, Route for approval, Block submit, Route to auditor, Flag to manager, Hold for auditor.

### Version history card
- Title "Version history", icon ph/clock-counter-clockwise top-right.
- Vertical timeline (purple line; current draft = hollow circle, published = filled check):
  - "v7 · draft" — "Cab limit ₹2,000 → ₹2,500 · Rajesh M."
  - "v6 · 01 Oct 2026" — "Tier-1 list adds Pune"
  - "v5 · 01 Jul 2026" — "Meals ₹1,200 → ₹1,500"
  - "v4 · 01 Apr 2026" — "Weekend flag introduced"
- Footer note (ph/lock, muted): "Every change is written to the audit trail"

## Interactions & states
- Editing a limit or "When breached" value marks the row "Changed" (warning chip, row highlight, old value struck/muted).
  Behaviour (inferred): limit cells are inline-editable numeric inputs; the design shows them as plain text.
- "Publish v7": Behaviour (inferred): confirm Dialog, then v7 becomes live from the "Effective from" date; history updates.
- "Discard draft": Behaviour (inferred): confirm, revert to v6 values, remove draft banner.
- "Effective from" must be a future date (inferred); claims are judged by the version live at submit time.
- "Applies to" lists (e.g. "Tier-1 cities (8)") — editing them is not designed.
- Clicking a history entry: not designed (could show a version diff).
- No-draft state (only live v6) not designed: suggest hiding the banner and showing "Create draft".

## Data & API
- Rules, versions, draft, effective date, publish/discard — Not yet in API: policy configuration endpoints (rules are seeded configuration per CLAUDE.md).
- Version change summaries and author — Not yet in API.
- Audit of policy changes — Not yet in API (audit exists only for claims).

## Build notes
- shadcn: Card, Table, Select, Input, Popover + Calendar (Effective from), Badge, Button, AlertDialog, Tooltip.
- Version timeline is custom (reuse with E5 claim timeline if the style matches).
- Keep `—` for rules with no numeric limit; `%` for sample audit.
- Track dirty state per row against the live version to drive the "Changed" chip.
