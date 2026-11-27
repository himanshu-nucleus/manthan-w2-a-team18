import { delay, http, HttpResponse, type HttpHandler } from 'msw'
import type { Delegation, PendingItem } from '@/features/approvals/api'
import { mockUsers } from '../data'

// MSW handlers for the approvals screens (tests + VITE_ENABLE_MOCKS=true).
// Fixtures live here (not in data.ts) and are mutable; call resetApprovalsMock() between tests.

const TOKEN_PREFIX = 'mock-token-'
const DAY = 86_400_000

function userFrom(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `${TOKEN_PREFIX}${u.id}` === token)
}

function apiError(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

function isoDaysAgo(days: number, hours = 0) {
  return new Date(Date.now() - days * DAY - hours * 3_600_000).toISOString()
}

function localDay(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * DAY)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function pendingItem(
  claimId: number,
  title: string,
  amount: string,
  outcome: string,
  submittedDaysAgo: number,
  options: { employeeId?: number; role?: string; onBehalfOf?: number | null } = {},
): PendingItem {
  const submitted = isoDaysAgo(submittedDaysAgo, 2)
  return {
    step: {
      id: claimId * 10,
      claim_id: claimId,
      round: 1,
      step_order: 1,
      approver_role: options.role ?? 'line_manager',
      assigned_approver_id: null,
      status: 'PENDING',
      acted_by_id: null,
      on_behalf_of_id: null,
      acted_at: null,
      comment: null,
      created_at: submitted,
    },
    claim: {
      id: claimId,
      employee_id: options.employeeId ?? 1,
      title,
      currency: 'INR',
      status: 'PENDING_APPROVAL',
      total_amount: amount,
      submitted_at: submitted,
      policy_outcome: outcome,
      submission_round: 1,
      version: 2,
      created_at: submitted,
      updated_at: submitted,
    },
    on_behalf_of_id: options.onBehalfOf ?? null,
  }
}

function initialPending(): PendingItem[] {
  return [
    pendingItem(101, 'Client visit Pune', '18500.00', 'ROUTE_FOR_APPROVAL', 6),
    pendingItem(102, 'Team lunch', '2400.00', 'AUTO_APPROVE', 4),
    pendingItem(103, 'Bengaluru offsite hotel', '42000.00', 'ROUTE_FOR_APPROVAL', 2, {
      onBehalfOf: 5,
    }),
    pendingItem(104, 'Airport cab', '950.00', 'AUTO_APPROVE', 1, { employeeId: 7 }),
  ]
}

function initialDelegations(): Delegation[] {
  return [
    {
      id: 1,
      delegator_id: 2,
      delegate_id: 4,
      from_date: localDay(3),
      to_date: localDay(6),
      reason: 'Annual leave',
      active: true,
      created_at: isoDaysAgo(1),
      cancelled_at: null,
    },
    {
      id: 2,
      delegator_id: 5,
      delegate_id: 2,
      from_date: localDay(-10),
      to_date: localDay(-8),
      reason: null,
      active: true,
      created_at: isoDaysAgo(12),
      cancelled_at: null,
    },
  ]
}

let pending = initialPending()
let delegations = initialDelegations()
let nextDelegationId = 100

export function resetApprovalsMock() {
  pending = initialPending()
  delegations = initialDelegations()
  nextDelegationId = 100
}

const ROLE_RANK: Record<string, number> = {
  employee: 0,
  line_manager: 1,
  finance_auditor: 2,
  finance_head: 3,
}

export const approvalsHandlers: HttpHandler[] = [
  http.get('/api/v1/approvals/pending', async ({ request }) => {
    const url = new URL(request.url)
    const limit = Number(url.searchParams.get('limit') ?? 50)
    const offset = Number(url.searchParams.get('offset') ?? 0)
    await delay()
    const user = userFrom(request)
    const items = user && user.role !== 'employee' ? pending : []
    return HttpResponse.json({
      items: items.slice(offset, offset + limit),
      total: items.length,
      limit,
      offset,
    })
  }),

  http.post('/api/v1/claims/:id/approve', async ({ params, request }) => {
    const id = Number(params.id)
    const body = (await request.json().catch(() => ({}))) as { step_id?: number }
    await delay()
    const item = pending.find((p) => p.claim.id === id)
    if (!item) return apiError(404, 'claim_not_found', 'Claim not found.')
    if (body.step_id !== undefined && body.step_id !== item.step.id) {
      return apiError(409, 'step_mismatch', 'This step has already moved on.')
    }
    pending = pending.filter((p) => p.claim.id !== id)
    return HttpResponse.json({
      ...item.claim,
      status: 'APPROVED',
      policy_evaluated_at: item.claim.submitted_at,
      created_by: item.claim.employee_id,
      updated_by: userFrom(request)?.id ?? 0,
      lines: [],
      attachments: [],
    })
  }),

  http.get('/api/v1/delegations/me', async ({ request }) => {
    await delay()
    const user = userFrom(request)
    if (!user) return apiError(401, 'not_authenticated', 'Not signed in.')
    const mine = delegations
      .filter((d) => d.delegator_id === user.id || d.delegate_id === user.id)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
    return HttpResponse.json(mine)
  }),

  http.post('/api/v1/delegations', async ({ request }) => {
    const body = (await request.json()) as {
      delegate_id: number
      from_date: string
      to_date: string
      reason?: string | null
    }
    await delay()
    const user = userFrom(request)
    if (!user) return apiError(401, 'not_authenticated', 'Not signed in.')
    if (user.role === 'employee') {
      return apiError(403, 'forbidden', 'Only approvers can delegate.')
    }
    const delegate = mockUsers.find((u) => u.id === body.delegate_id)
    if (!delegate) return apiError(422, 'delegation_invalid', 'The delegate does not exist.')
    if (delegate.id === user.id) {
      return apiError(422, 'delegation_invalid', 'You cannot delegate to yourself.')
    }
    if (ROLE_RANK[delegate.role] < ROLE_RANK[user.role]) {
      return apiError(
        422,
        'delegation_invalid',
        'The delegate must have the same or a higher role than you.',
      )
    }
    const created: Delegation = {
      id: nextDelegationId++,
      delegator_id: user.id,
      delegate_id: body.delegate_id,
      from_date: body.from_date,
      to_date: body.to_date,
      reason: body.reason ?? null,
      active: true,
      created_at: new Date().toISOString(),
      cancelled_at: null,
    }
    delegations = [created, ...delegations]
    return HttpResponse.json(created, { status: 201 })
  }),

  http.delete('/api/v1/delegations/:id', async ({ params, request }) => {
    const id = Number(params.id)
    await delay()
    const user = userFrom(request)
    const found = delegations.find((d) => d.id === id && d.delegator_id === user?.id)
    if (!found) return apiError(404, 'delegation_not_found', 'Delegation not found.')
    delegations = delegations.map((d) =>
      d.id === id ? { ...d, active: false, cancelled_at: new Date().toISOString() } : d,
    )
    return new HttpResponse(null, { status: 204 })
  }),
]
