import { http, HttpResponse, type HttpHandler } from 'msw'
import type { DashboardSummary } from '@/features/insights/summary-api'
import { mockUsers } from '../data'

// MSW handler for the finance dashboard (tests + VITE_ENABLE_MOCKS=true).

const FINANCE = new Set(['finance_head', 'finance_auditor'])

function userFrom(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `mock-token-${u.id}` === token)
}

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function mockDashboardSummary(month?: string | null): DashboardSummary {
  const now = new Date()
  const selected = month ?? monthKey(now)
  const [y, m] = selected.split('-').map(Number)
  const monthly_spend = Array.from({ length: 6 }, (_, i) => {
    const d = new Date(y, m - 1 - (5 - i), 1)
    return { month: monthKey(d), claims: 10 + i * 3, amount: `${(80000 + i * 15000).toFixed(2)}` }
  })
  return {
    month: selected,
    generated_at: now.toISOString(),
    active_employees: 42,
    kpis: {
      claims: { value: 25, previous: 20 },
      total_spend: { value: '155000.00', previous: '140000.00' },
      policy_violations: { lines: 4, total_lines: 80, rate_percent: 5, previous_lines: 6 },
      approval_time: { average_hours: 18.5, previous_average_hours: 24, approved_claims: 19 },
      ready_for_payout: { claims: 3, amount: '42000.00' },
    },
    needs_action: {
      my_pending_approvals: 2,
      high_value_pending: {
        threshold: '50000.00',
        count: 1,
        claims: [
          {
            id: 301,
            title: 'Client offsite',
            employee_id: 1,
            employee_name: 'Asha Rao',
            total_amount: '72000.00',
          },
        ],
      },
    },
    monthly_spend,
    spend_by_category: [
      { category: 'airfare', amount: '60000.00' },
      { category: 'hotel', amount: '45000.00' },
      { category: 'meal', amount: '20000.00' },
    ],
    spend_by_department: [
      { department: 'Engineering', amount: '90000.00' },
      { department: 'Sales', amount: '65000.00' },
    ],
    recent_events: [
      {
        id: 1,
        created_at: now.toISOString(),
        actor_id: 4,
        actor_name: 'Finance Head',
        action: 'APPROVED',
        entity_type: 'claim',
        entity_id: 301,
      },
      {
        id: 2,
        created_at: now.toISOString(),
        actor_id: 3,
        actor_name: 'Finance Auditor',
        action: 'BATCH_CREATED',
        entity_type: 'payout_batch',
        entity_id: 7,
      },
    ],
  }
}

export const dashboardHandlers: HttpHandler[] = [
  http.get('/api/v1/dashboard/summary', ({ request }) => {
    const user = userFrom(request)
    if (!user) {
      return HttpResponse.json(
        { error: { code: 'unauthorized', message: 'Not signed in' } },
        { status: 401 },
      )
    }
    if (!FINANCE.has(user.role)) {
      return HttpResponse.json(
        { error: { code: 'forbidden', message: 'Finance roles only' } },
        { status: 403 },
      )
    }
    return HttpResponse.json(mockDashboardSummary(new URL(request.url).searchParams.get('month')))
  }),
]
