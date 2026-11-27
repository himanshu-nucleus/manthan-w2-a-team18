# ExpenseFlow — Design System (shadcn/ui + Phosphor)

This document describes the ExpenseFlow UI as built in Figma (page **ExpenseFlow – UI**). It explains how to build it in code with **shadcn/ui**, **Tailwind CSS v4** and **Phosphor icons**. The tokens are in `index.css`.

> Source of truth: the Figma variable collection **shadcn colors → mode "ExpenseFlow"**, plus the kit's radius, spacing, typography and shadow styles. If Figma changes, update `index.css` first, then this file.

---

## 1. Principles

1. **The policy is always visible.** Every expense line shows its verdict next to it (within policy, needs approval, auto-rejected). The verdict names the rule, the limit and the actual amount.
2. **Next step first.** Every screen answers "what do I need to do?" before "what happened?". Use action lists, a primary button in the header, and a "With / next step" column.
3. **One purple accent.** Violet `#7C3AED` is the only brand colour for interactive elements. Status meaning comes from the status tones (green, amber, red, blue), never from purple.
4. **Calm surfaces with a little magic.** Use a light lavender background, white cards and soft borders. Keep the dark "night sky" gradient for hero surfaces only: the active nav item, the promo card, the login panel and the bulk-action bar.
5. **Roles see only their own data.** Each role (Employee, Manager, Auditor, Finance head) gets its own sidebar and its own dashboard numbers.

---

## 2. Setup

```bash
npx shadcn@latest init            # choose Tailwind v4, CSS variables, base color: neutral
npm i @phosphor-icons/react geist
npx shadcn@latest add button input label select checkbox tabs badge avatar card table \
  dialog sheet separator tooltip dropdown-menu textarea radio-group switch sonner
```

- Replace the generated `app/globals.css` (or `src/index.css`) with the provided `index.css`.
- Load the fonts: `import { GeistSans } from "geist/font/sans"` and `GeistMono` (Next.js), or self-host Geist.
- In `components.json`, set `"iconLibrary": "phosphor"` if your shadcn CLI supports it. Otherwise, swap `lucide-react` imports for Phosphor by hand (see §8).

---

## 3. Color tokens

### 3.1 Core (light, "ExpenseFlow" mode)

| Token                    | Hex       | Used for                                                               |
| ------------------------ | --------- | ---------------------------------------------------------------------- |
| `--background`           | `#F7F6FB` | App canvas behind cards                                                |
| `--foreground`           | `#16121F` | Body text, headings                                                    |
| `--card` / `--popover`   | `#FFFFFF` | Cards, sheets, dialogs, dropdowns                                      |
| `--primary`              | `#7C3AED` | Primary buttons, links, active tab, checkbox, nav counts               |
| `--primary-foreground`   | `#FFFFFF` | Text and icons on primary                                              |
| `--secondary`            | `#F3EFFF` | Secondary buttons, soft fills                                          |
| `--secondary-foreground` | `#5B21B6` | Text on secondary                                                      |
| `--accent`               | `#F3EFFF` | Icon tiles, hover rows, selected options, highlighted table rows (60%) |
| `--accent-foreground`    | `#4C1D95` | Text on accent                                                         |
| `--muted`                | `#F4F3F8` | Table headers, tab list, inline stat tiles                             |
| `--muted-foreground`     | `#6B6780` | Secondary text, captions, table header labels                          |
| `--destructive`          | `#DC2626` | Reject and delete actions                                              |
| `--border`               | `#ECEAF2` | Card and table borders, dividers                                       |
| `--input`                | `#E2DFEB` | Input borders                                                          |
| `--ring`                 | `#A78BFA` | Focus ring                                                             |

### 3.2 Sidebar

| Token                  | Hex       | Notes                                                |
| ---------------------- | --------- | ---------------------------------------------------- |
| `--sidebar`            | `#FFFFFF` | Sidebar surface, 1px right border                    |
| `--sidebar-foreground` | `#3F3B4D` | Inactive nav label and icon                          |
| `--sidebar-primary`    | `#120B24` | Active item base; in practice drawn with `.bg-night` |
| `--sidebar-accent`     | `#F3EFFF` | Role switcher pill, hover                            |
| `--sidebar-border`     | `#ECEAF2` | Divider between nav groups                           |

### 3.3 Status tones (ExpenseFlow extension)

Each tone has three tokens: background, foreground and border. Use them for the **Status Chip**, banners and action-row icon tiles.

| Tone      | bg / fg / border                  | Claim states that use it                                                                                        |
| --------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `success` | `#ECFDF3` / `#067647` / `#ABEFC6` | Approved, Paid, Within policy, Auto-approve, Cleared, Clean                                                     |
| `warning` | `#FFFAEB` / `#B54708` / `#FEDF89` | Sent back, Needs approval, Route for approval, Over limit (routed), Possible duplicate (employee view), Changed |
| `danger`  | `#FEF3F2` / `#B42318` / `#FECDCA` | Auto-rejected, Over daily limit, Receipt required, Duplicate (auditor view), Line rejected                      |
| `info`    | `#EFF8FF` / `#175CD3` / `#B2DDFF` | Pending manager, Pending auditor, Over ₹25,000, Submitted, Resubmitted                                          |
| `neutral` | `#F4F3F8` / `#3F3B4D` / `#E2DFEB` | Draft, generic metadata                                                                                         |
| `brand`   | `#F5F3FF` / `#6D28D9` / `#DDD6FE` | Weekend flag, Sampled 10%, Policy version, AI and "info about the system"                                       |

Default chip icons: success → `CheckCircle`, warning → `Warning`, danger → `XCircle`, info → `Info`, neutral → `Clock`, brand → `Sparkle`.

### 3.4 Gradients

| Token / class                               | Value                                | Where                                                                                |
| ------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------ |
| `--gradient-brand` / `.text-gradient-brand` | `#7E22CE → #2563EB` (90°)            | Greeting headline, logo mark, success check, sign-in title                           |
| `--gradient-brand-soft`                     | `#C4B5FD → #93C5FD`                  | Second headline line on the dark login panel                                         |
| `--gradient-night` / `.bg-night`            | `#1A0B3B → #120B24 → #3B1D7A` (135°) | Active nav item, promo card, login panel, bulk-action bar, AI send button            |
| `--gradient-bar`                            | `#7C3AED → #2563EB` (vertical)       | Highlighted (first or largest) bar in charts; horizontal bars use the brand gradient |

### 3.5 Charts

`--chart-1 … --chart-5` = `#7C3AED`, `#2563EB`, `#A78BFA`, `#93C5FD`, `#4C1D95`. Bars that aren't highlighted use `primary` at 25–85% opacity, scaled to their value. Line charts use a 3px `#7C3AED` stroke with a violet area fill fading from 25% to 0%.

> Note: the kit's original `chart colors/*` variables are still the shadcn blue scale. The ExpenseFlow screens use the violet values above.

### 3.6 Dark mode

Dark mode is **not designed in Figma yet**. The `.dark` block in `index.css` is a proposed starting point that keeps the same hues, and the topbar toggle switches to it. Design and check it in Figma before you ship it.

---

## 4. Typography

The font family is **Geist**; numbers and code use **Geist Mono**. All styles map to the Figma text styles.

| Figma style            | Size / line height | Weight                          | Tailwind                   | Used for                                        |
| ---------------------- | ------------------ | ------------------------------- | -------------------------- | ----------------------------------------------- |
| greeting (custom)      | 34 / 42            | Medium + `.text-gradient-brand` | `text-display font-medium` | Dashboard greeting headline                     |
| heading 1              | 40 / 40            | Medium                          | `text-h1 font-medium`      | Login hero (48/56)                              |
| heading 2              | 26 / 26            | Medium                          | `text-h2 font-medium`      | Success title; KPI value (30)                   |
| heading 3              | 22 / 26.4          | Medium                          | `text-h3 font-medium`      | Page titles ("My claims")                       |
| heading 4              | 18 / 21.6          | Medium                          | `text-h4 font-medium`      | Drawer titles, totals                           |
| paragraph large/bold   | 18 / 27            | SemiBold                        | `text-lg font-semibold`    | Sidebar wordmark                                |
| paragraph/bold         | 16 / 24            | SemiBold                        | `text-base font-semibold`  | Card titles                                     |
| paragraph/medium       | 16 / 24            | Medium                          | `text-base font-medium`    | "Hi Ananya Sharma"                              |
| paragraph small/normal | 14 / 20            | Regular                         | `text-sm`                  | **App default**, table cells                    |
| paragraph small/medium | 14 / 20            | Medium                          | `text-sm font-medium`      | Nav labels, amounts, buttons                    |
| paragraph small/bold   | 14 / 20            | SemiBold                        | `text-sm font-semibold`    | Row titles, banner titles                       |
| paragraph mini/normal  | 12 / 16            | Regular                         | `text-xs`                  | Captions, helper text (`text-muted-foreground`) |
| paragraph mini/medium  | 12 / 16            | Medium                          | `text-xs font-medium`      | Field labels, table headers, chips              |
| monospace small        | 14 / 20            | Regular                         | `font-mono text-sm`        | Bank-file CSV preview                           |

Rules: use sentence case everywhere. Claim IDs appear in `text-primary font-medium` (for example `EXP-2026-0813`). Add the `.tabular` class to amounts.

---

## 5. Spacing, radius, elevation

**Spacing** follows the Figma "spacing" collection, which is the Tailwind 4px scale (2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64…).

| Context                    | Value                                                    |
| -------------------------- | -------------------------------------------------------- |
| Page padding (main area)   | `pt-6 px-8 pb-10` (24 / 32 / 40)                         |
| Gap between page sections  | `gap-6` (24)                                             |
| Gap between cards in a row | `gap-5` (20)                                             |
| Card padding               | `p-5` (20); hero overview card `p-6`                     |
| Inside a card              | `gap-3.5` (14)                                           |
| Table cell                 | `px-4 py-3` (header `py-2.5`)                            |
| Sidebar                    | `w-[260px] px-4 pt-6 pb-4`, nav item `h-10 px-3 gap-2.5` |

**Radius**

| Token                     | px  | Used for                                                       |
| ------------------------- | --- | -------------------------------------------------------------- |
| `rounded-md`              | 8   | Small tiles, chart bars (top corners)                          |
| `rounded-lg` (`--radius`) | 10  | Icon tiles (32px), logo mark, inputs and buttons (kit default) |
| `rounded-nav`             | 12  | Sidebar nav items, tab list, inline stat tiles                 |
| `rounded-2xl`             | 16  | Banners, action rows, option cards                             |
| `rounded-card`            | 20  | Cards, KPI cards                                               |
| `rounded-promo`           | 24  | Promo card, dialogs, sheets (left corners only)                |
| `rounded-hero`            | 28  | Dashboard overview card, success card                          |
| `rounded-full`            | —   | Chips, search, topbar pills, avatars, AI bar                   |

**Elevation:** cards use `border` plus `shadow-xs` (KPI) or no shadow. Dialogs and sheets use `shadow-2xl`. Receipt previews use `shadow-md`. The AI bar uses `shadow-ai`. The modal scrim is `#120B24` at 40%.

---

## 6. Layout

- **Desktop frame:** 1440 wide, minimum height 1024. Columns are the sidebar (260 fixed) and the main area (fills the rest).
- **Topbar (inside main):** search pill (380, `rounded-full`, ⌘K hint) · spacer · light/dark segmented toggle · context pill (department, `Buildings` icon) · bell button (42, count badge) · avatar (Large).
- **Page header:** a breadcrumb in `text-xs text-muted-foreground`, then the H3 title with optional chips, with actions right-aligned (outline button, then primary button).
- **Dashboards (all roles share one template):**
  1. Greeting: "Hi {name}" plus a gradient headline and a sub-line.
  2. **Overview card** (`rounded-hero`, violet and blue glow): title + period select + more menu; five KPI cards; insight lines that start with a `Sparkle` (fill) icon and end in a link; the AI prompt bar.
  3. A row with an **action list** ("Needs your action") on the left (fill width) and a role panel on the right (400–500px: policy limits, team spend, queue by reason, monthly spend).
  4. A recent-activity table card.
- **Two-column detail pages:** content column (fill) and side column (320–420) for timeline, totals, policy check and version history.
- **Overlays:** sheets slide in from the right (540–600 wide, full height). Dialogs are 640 wide and centred, 110px from the top.

---

## 7. Components

### 7.1 shadcn components used (kit "Nova" variants)

| shadcn                                           | Usage notes                                                                                                                                                                            |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Button`                                         | Variants used: `default` (primary), `outline`, `secondary`, `ghost`, `destructive`. Sizes: `default` (32), `sm`, `xs` (in table cells), `lg` (login). Icon on the left, Phosphor 16px. |
| `Input`                                          | Regular height 32 (login uses large). Label above in `text-xs font-medium text-muted-foreground`, 6–8px gap.                                                                           |
| `Select`                                         | Filters ("Date: This year", "Department: All") and the "When breached" column on the Policy rules screen.                                                                              |
| `Checkbox`                                       | Row selection for bulk approve. Disabled (not checked) on rows that can't be bulk-approved.                                                                                            |
| `Tabs`                                           | Segmented `TabsList` on `bg-muted rounded-xl p-[3px]`, with a count badge in each tab.                                                                                                 |
| `Badge`                                          | Neutral counts in card headers ("3"). For states, use **StatusChip**, not Badge.                                                                                                       |
| `Avatar`                                         | 24 in tables and the logout pill, 40 in the topbar and history card.                                                                                                                   |
| `Card`                                           | Override the radius to `rounded-card`. Use `p-0 overflow-hidden` when the card wraps a table.                                                                                          |
| `Table`                                          | Header row `bg-muted text-xs font-medium text-muted-foreground`. Rows `border-b`. Highlighted row `bg-accent/60`. Right-align amounts.                                                 |
| `Sheet`                                          | M3 review claim, M4 out of office, N3 add expense.                                                                                                                                     |
| `Dialog`                                         | N1 start a new claim.                                                                                                                                                                  |
| `Separator`, `Tooltip`, `DropdownMenu`, `Sonner` | General use.                                                                                                                                                                           |

### 7.2 ExpenseFlow components (local Figma components → build as React components)

**StatusChip** — `tone: success | warning | danger | info | neutral | brand`, `label`

```tsx
<span className="inline-flex items-center gap-1.5 rounded-full border border-warning-border bg-warning px-2 py-0.5 pr-2.5 text-xs font-medium text-warning-foreground">
  <Warning size={13} /> Sent back
</span>
```

**SidebarNavItem** — `label`, `icon`, `count?`, `active`

- Default: `h-10 rounded-[12px] px-3 gap-2.5 text-sm font-medium text-sidebar-foreground`, icon 18.
- Active: `.bg-night text-white`, a few 1–2.5px white sparkle dots on the right, and the count shown as `bg-white/15`.
- Count (default state): `rounded-full bg-primary px-1.5 text-xs font-semibold text-white`.

**Sidebar (per role)** — logo (32px gradient tile + `Receipt` icon + "ExpenseFlow"), a "Workspace" row with the role switcher pill (`bg-accent`, `UserSwitch` icon), the role's nav items, a separator, then Notifications · Policy guide · Settings. After a spacer come the **PromoCard** and the logout pill (`bg-muted rounded-full`, avatar, name, "Log out of your account", `SignOut` icon).

| Role         | Nav items                                                                                                      |
| ------------ | -------------------------------------------------------------------------------------------------------------- |
| Employee     | Dashboard · My claims (18) · New claim                                                                         |
| Manager      | Team dashboard · Approvals (7) · Out of office                                                                 |
| Auditor      | Dashboard · Audit queue (48) · Audit history                                                                   |
| Finance head | Dashboard · Spend analytics · Approvals (2) · Payout batches · Policy rules · Approvals & people · Audit trail |

**KpiCard** — `label`, `value`, `sub`, `icon`. White, `rounded-card`, border, `shadow-xs`, `p-[18px]`. Icon in a 32px `bg-accent` tile (`text-primary`, 18px). Value at 30px medium; sub-line in `text-xs text-muted-foreground`. In a row, cards share the width and stretch to equal height.

**PromoCard** — `.bg-night rounded-promo p-5`, violet glow, sparkle dots. Content: an eyebrow line (`Sparkle` fill icon + `text-violet-300 text-xs`), a 30px white figure, body text at 75% opacity, and a white button with a primary label and `RocketLaunch` icon. Content by role: Owed to you / Avg approval time / At risk this month / Ready for payout.

**ActionRow** (inside the "Needs your action" card) — `rounded-2xl border p-3.5 gap-3`. A 32px tone tile with an icon, then a title with a StatusChip, a one-line reason in `text-xs muted`, and a small button (primary for the first, most urgent item; outline for the rest).

**AIPromptBar** — `rounded-full border-[1.5px] border-violet-300 shadow-ai pl-[18px] p-2`. Placeholder "Ask ExpenseFlow AI anything…", then two `.chip-prompt` suggestions, then a 40px `.bg-night` round send button with a `Sparkle` (fill) icon.

**PolicyBanner** — `rounded-2xl border p-4 gap-3` in a status tone. A 32px white icon tile, a bold title, body text in `text-muted-foreground`, and optional inline actions or an input.

**Timeline** — 20px dots: done = `bg-primary` with a white `Check`; current = `bg-accent` with a 2px primary ring; future = `bg-muted`. The connector line is 2px (`primary` when done, otherwise `border`). Each step has a bold title and a caption.

**Stepper (new-claim flow)** — four steps (Claim details → Add expenses → Receipts & policy → Review & submit) in a white `rounded-[18px]` bar. Each step is a 26px numbered dot with the same states as the Timeline.

**BulkActionBar** — `.bg-night rounded-[18px] px-5 py-3`. It says "{n} claims selected · ₹total", gives a muted reason why some rows are excluded, and has Clear (ghost) and Approve n (secondary) buttons.

**Empty state** — a 96px `bg-accent` circle around a 60px gradient circle with an icon, an H4, a muted line, a primary button, and a dashed `bg-accent` drop zone (`border-dashed border-primary/50`).

**Receipt drop zone** — `rounded-card bg-accent border-[1.5px] border-dashed border-primary/50 p-6`, with a 44px white circle holding a `CloudArrowUp` icon.

**Login (L1)** — split layout: a `.bg-night` brand panel (640px, `rounded-[32px]`, inset 16px) and a centred 440px form with the title "Sign in to your account" (`.text-gradient-brand`), Work email, Password and a full-width **Sign in** button (`size="lg"`).

---

## 8. Icons — Phosphor

```tsx
import { Receipt, Plus, Warning } from "@phosphor-icons/react";
// Optional global defaults
<IconContext.Provider value={{ size: 16, weight: "regular", mirrored: false }}>
```

- **Weight:** `regular` everywhere. Use `fill` only for `Sparkle` (AI, insights, promo eyebrow).
- **Sizes:** 12–14 in chips and inline text · 16 in buttons, inputs and table cells · 18 in nav, KPI tiles and banners · 20–24 in headers and drop zones · 28+ in empty states.
- **Colour:** icons use `currentColor`. Set the colour on the parent (`text-primary`, `text-muted-foreground`, or a tone foreground).

| Meaning                    | Phosphor icon                                                           |
| -------------------------- | ----------------------------------------------------------------------- |
| Dashboard                  | `SquaresFour`                                                           |
| Claims / receipt           | `Receipt`                                                               |
| New / add                  | `Plus`                                                                  |
| Approvals queue            | `ListChecks`                                                            |
| Audit queue / policy check | `ShieldCheck`                                                           |
| History / audit trail      | `ClockCounterClockwise`                                                 |
| Spend analytics            | `ChartLineUp`, `ChartBar`                                               |
| Payout batch               | `Bank`                                                                  |
| Policy rules               | `Scales`                                                                |
| Approval chain             | `TreeStructure`                                                         |
| Out of office              | `CalendarX`                                                             |
| Role switch / delegate     | `UserSwitch`                                                            |
| Notifications              | `Bell`                                                                  |
| Settings                   | `Gear`                                                                  |
| Search                     | `MagnifyingGlass`                                                       |
| Department context         | `Buildings`                                                             |
| Theme                      | `Moon`, `Sun`                                                           |
| Hotel / meals / cab / air  | `Bed`, `ForkKnife`, `Taxi`, `AirplaneTilt`                              |
| Amount / wallet            | `CurrencyInr`, `Wallet`                                                 |
| Send back                  | `ArrowUUpLeft`                                                          |
| Submit / send              | `PaperPlaneTilt`                                                        |
| Upload receipt             | `UploadSimple`, `CloudArrowUp`                                          |
| Download / export          | `DownloadSimple`, `Export`, `FileCsv`                                   |
| Duplicate                  | `Copy`                                                                  |
| Weekend / dates            | `CalendarBlank`                                                         |
| Sample audit               | `Flag`                                                                  |
| Locked / append-only       | `LockSimple`                                                            |
| Draft / edit               | `NotePencil`, `PencilSimple`                                            |
| Status                     | `CheckCircle`, `Warning`, `XCircle`, `Info`, `Clock`, `HourglassMedium` |
| AI                         | `Sparkle` (fill)                                                        |
| Promo action               | `RocketLaunch`                                                          |
| Log out                    | `SignOut`                                                               |
| More                       | `DotsThreeVertical`                                                     |
| Close                      | `X`                                                                     |

---

## 9. Content and data formatting

- **Currency:** Indian grouping with the ₹ symbol: `₹1,00,000`, `₹38,130`. Use lakh for large totals: `₹4.6 L`, `₹42.7 L`. Format with `new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 })`.
- **Dates:** `14 Nov`, `14 Nov, 16:20`, `10–12 Nov`; include the year only when it isn't the current year. Relative ages in tables: `5 h`, `2 d`.
- **IDs:** claims `EXP-2026-0813`; batches `NOV-2026-02`; employees `E1042`.
- **Policy reasons** always state the rule, the limit and the actual value: "Hotel ₹6,800/night is over the ₹6,000 tier-1 limit."
- **Tone:** plain and specific. Buttons are verbs ("Approve ₹27,400", "Send back", "Create draft").

---

## 10. Accessibility

- Text contrast: `--foreground` and `--muted-foreground` on white and on `--background` meet WCAG AA for body text. Primary `#7C3AED` with white text passes AA for normal text.
- Never use colour alone for state: every StatusChip has an icon and a label.
- Focus: a 2px `--ring` outline with a 2px offset on every interactive element. Sheets and dialogs trap focus and close on Esc.
- Each table row selection checkbox needs an `aria-label` ("Select EXP-2026-0813"). Rows that are excluded from bulk actions are `disabled` and have a tooltip explaining why.
- Icon-only buttons (bell, close, more) need `aria-label`.

---

## 11. Screen inventory (Figma page "ExpenseFlow – UI")

| Section              | Screens                                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Employee             | E1 Dashboard · E2 My claims · E3 Draft with expenses · E4 Review & submit · E5 Claim detail and clarification                   |
| New claim flow       | N1 Start a new claim (dialog) · N2 Empty draft · N3 Add expense (sheet) · N6 Claim submitted                                    |
| Line manager         | M1 Dashboard · M2 Approvals queue · M3 Review claim (sheet) · M4 Out of office and delegation (sheet)                           |
| Finance auditor      | A0 Dashboard · A1 Audit queue · A2 Duplicate detection · A3 Audit history                                                       |
| Finance head · Admin | F0 Dashboard · F1 Spend analytics · F2 Payout batches and CSV · F3 Policy rules · F4 Approval chain and people · F5 Audit trail |
| Authentication       | L1 Login                                                                                                                        |

Local components live on the board **ExpenseFlow Components**: Status Chip, Sidebar Nav Item, KPI Card, Sidebar Promo Card, Topbar, and Sidebar / Employee · Manager · Auditor · Finance head. The 64 Phosphor icons are under **Phosphor Icons (regular)**.
