import { describe, expect, it } from 'vitest'
import type { ClaimSummary } from '@/features/claims/api'
import { aggregateCategories, aggregateClaims, formatDuration, latestSubmitted } from './aggregate'

const base: ClaimSummary = {
  id: 1,
  employee_id: 1,
  title: null,
  currency: 'INR',
  status: 'DRAFT',
  total_amount: '0',
  submitted_at: null,
  policy_outcome: null,
  approved_at: null,
  paid_at: null,
  submission_round: 1,
  version: 1,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
}
const c = (o: Partial<ClaimSummary>): ClaimSummary => ({ ...base, ...o })
const now = new Date(2026, 10, 27)

describe('aggregateClaims', () => {
  const claims = [
    c({ id: 1, status: 'DRAFT', total_amount: '999' }),
    c({
      id: 2,
      status: 'APPROVED',
      total_amount: '1000.50',
      submitted_at: '2026-11-10T10:00:00',
      approved_at: '2026-11-10T16:00:00',
      policy_outcome: 'ROUTE_FOR_APPROVAL',
    }),
    c({
      id: 3,
      status: 'PAID',
      total_amount: '2000',
      submitted_at: '2026-10-05T10:00:00',
      approved_at: '2026-10-07T10:00:00',
      paid_at: '2026-10-08T10:00:00',
      policy_outcome: 'AUTO_APPROVE',
    }),
    c({
      id: 4,
      status: 'AUTO_REJECTED',
      total_amount: '500',
      submitted_at: '2026-11-11T10:00:00',
      policy_outcome: 'AUTO_REJECT',
    }),
    c({
      id: 5,
      status: 'DUPLICATE',
      total_amount: '300',
      submitted_at: '2025-01-11T10:00:00',
      policy_outcome: 'MARK_DUPLICATE',
    }),
  ]
  const s = aggregateClaims(claims, { now })

  it('counts claims and spend', () => {
    expect(s.totalClaims).toBe(5)
    expect(s.submittedClaims).toBe(4)
    expect(s.totalSpend).toBeCloseTo(3000.5)
  })
  it('counts violations per outcome', () => {
    expect(s.violations).toBe(3)
    expect(s.violationsByOutcome).toEqual({
      ROUTE_FOR_APPROVAL: 1,
      AUTO_REJECT: 1,
      MARK_DUPLICATE: 1,
    })
  })
  it('averages approval time', () => {
    expect(s.approvedWithTiming).toBe(2)
    expect(s.avgApprovalHours).toBeCloseTo(27)
  })
  it('computes ready-for-payout', () => {
    expect(s.payoutCount).toBe(1)
    expect(s.payoutAmount).toBeCloseTo(1000.5)
  })
  it('buckets the last 6 months by submitted_at', () => {
    expect(s.byMonth.map((b) => b.key)).toEqual([
      '2026-06',
      '2026-07',
      '2026-08',
      '2026-09',
      '2026-10',
      '2026-11',
    ])
    expect(s.byMonth[5].amount).toBeCloseTo(1500.5)
    expect(s.byMonth[4].amount).toBe(2000)
  })
  it('breaks down by status', () => {
    expect(s.byStatus.find((b) => b.status === 'PAID')).toEqual({
      status: 'PAID',
      count: 1,
      amount: 2000,
    })
  })
  it('handles empty input', () => {
    const e = aggregateClaims([], { now })
    expect(e.avgApprovalHours).toBeNull()
    expect(e.totalSpend).toBe(0)
  })
})

describe('helpers', () => {
  it('sums categories', () => {
    const line = { category: 'meal', amount: '100' }
    expect(
      aggregateCategories([
        { lines: [line, { ...line, category: 'hotel', amount: '500' }] as never },
        { lines: [line, { ...line, category: null }] as never },
      ]),
    ).toEqual([
      { category: 'hotel', amount: 500 },
      { category: 'meal', amount: 200 },
      { category: 'other', amount: 100 },
    ])
  })
  it('formats durations', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(5)).toBe('5.0 h')
    expect(formatDuration(48)).toBe('2.0 d')
  })
  it('picks latest submitted', () => {
    const list = [
      c({ id: 1, submitted_at: '2026-01-01' }),
      c({ id: 2 }),
      c({ id: 3, submitted_at: '2026-02-01' }),
    ]
    expect(latestSubmitted(list, 1).map((x) => x.id)).toEqual([3])
  })
})
