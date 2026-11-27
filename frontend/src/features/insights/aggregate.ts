import type { Claim, ClaimSummary } from '@/features/claims/api'

/** Statuses whose amount counts as company spend. */
export const SPEND_STATUSES: readonly string[] = ['APPROVED', 'AUTO_APPROVED', 'PAID']
/** Statuses ready for the next payout batch (approved, not yet paid). */
export const PAYABLE_STATUSES: readonly string[] = ['APPROVED', 'AUTO_APPROVED']
/** Claim-level policy outcomes that count as a violation. */
export const VIOLATION_OUTCOMES = ['ROUTE_FOR_APPROVAL', 'AUTO_REJECT', 'MARK_DUPLICATE'] as const

export interface MonthBucket {
  key: string // YYYY-MM
  label: string // "Nov"
  amount: number
  count: number
}

export interface InsightsSummary {
  totalClaims: number
  submittedClaims: number
  totalSpend: number
  violations: number
  violationsByOutcome: Record<string, number>
  avgApprovalHours: number | null
  approvedWithTiming: number
  payoutCount: number
  payoutAmount: number
  byStatus: { status: string; count: number; amount: number }[]
  byMonth: MonthBucket[]
}

const num = (value: string | null | undefined) => {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : 0
}

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
const monthLabel = new Intl.DateTimeFormat('en-IN', { month: 'short' })

export function aggregateClaims(
  claims: ClaimSummary[],
  { now = new Date(), months = 6 }: { now?: Date; months?: number } = {},
): InsightsSummary {
  const violationsByOutcome: Record<string, number> = Object.fromEntries(
    VIOLATION_OUTCOMES.map((o) => [o, 0]),
  )
  const statusMap = new Map<string, { count: number; amount: number }>()
  const byMonth: MonthBucket[] = []
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    byMonth.push({ key: monthKey(d), label: monthLabel.format(d), amount: 0, count: 0 })
  }
  const monthIndex = new Map(byMonth.map((b, i) => [b.key, i]))

  let totalSpend = 0
  let submittedClaims = 0
  let violations = 0
  let payoutCount = 0
  let payoutAmount = 0
  let approvalMs = 0
  let approvedWithTiming = 0

  for (const c of claims) {
    const amount = num(c.total_amount)
    const s = statusMap.get(c.status) ?? { count: 0, amount: 0 }
    s.count += 1
    s.amount += amount
    statusMap.set(c.status, s)

    if (SPEND_STATUSES.includes(c.status)) totalSpend += amount
    if (PAYABLE_STATUSES.includes(c.status) && !c.paid_at) {
      payoutCount += 1
      payoutAmount += amount
    }
    if (c.policy_outcome && c.policy_outcome in violationsByOutcome) {
      violations += 1
      violationsByOutcome[c.policy_outcome] += 1
    }
    if (c.submitted_at) {
      submittedClaims += 1
      const idx = monthIndex.get(monthKey(new Date(c.submitted_at)))
      if (idx !== undefined) {
        byMonth[idx].amount += amount
        byMonth[idx].count += 1
      }
      if (c.approved_at) {
        const diff = new Date(c.approved_at).getTime() - new Date(c.submitted_at).getTime()
        if (Number.isFinite(diff) && diff >= 0) {
          approvalMs += diff
          approvedWithTiming += 1
        }
      }
    }
  }

  return {
    totalClaims: claims.length,
    submittedClaims,
    totalSpend,
    violations,
    violationsByOutcome,
    avgApprovalHours: approvedWithTiming ? approvalMs / approvedWithTiming / 3_600_000 : null,
    approvedWithTiming,
    payoutCount,
    payoutAmount,
    byStatus: [...statusMap.entries()]
      .map(([status, v]) => ({ status, ...v }))
      .sort((a, b) => b.count - a.count),
    byMonth,
  }
}

/** Sum line amounts per category across claim details. */
export function aggregateCategories(claims: Pick<Claim, 'lines'>[]) {
  const map = new Map<string, number>()
  for (const c of claims) {
    for (const line of c.lines) {
      const key = line.category ?? 'other'
      map.set(key, (map.get(key) ?? 0) + num(line.amount))
    }
  }
  return [...map.entries()]
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount)
}

/** `5.2 h` under a day, else `2.4 d`. */
export function formatDuration(hours: number | null) {
  if (hours === null) return '—'
  return hours < 24 ? `${hours.toFixed(1)} h` : `${(hours / 24).toFixed(1)} d`
}

/** Most recent submitted claims (by submitted_at desc). */
export function latestSubmitted(claims: ClaimSummary[], n: number) {
  return claims
    .filter((c) => c.submitted_at)
    .sort((a, b) => (b.submitted_at ?? '').localeCompare(a.submitted_at ?? ''))
    .slice(0, n)
}
