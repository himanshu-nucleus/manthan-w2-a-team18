import { http, HttpResponse, type HttpHandler } from 'msw'
import type { AuditEvent } from '@/features/claims/api'
import { mockUsers } from '../data'

// MSW handlers for the audit trail screen (tests + VITE_ENABLE_MOCKS=true).

const TOKEN_PREFIX = 'mock-token-'
const FINANCE = new Set(['finance_head', 'finance_auditor'])

function userFrom(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `${TOKEN_PREFIX}${u.id}` === token)
}

function apiError(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

function event(id: number, partial: Partial<AuditEvent>): AuditEvent {
  return {
    id,
    entity_type: 'claim',
    entity_id: 101,
    claim_id: 101,
    action: 'SUBMITTED',
    changes: {},
    actor_id: 1,
    actor_role: 'employee',
    on_behalf_of_id: null,
    comment: null,
    ip_address: '127.0.0.1',
    request_id: `req-${id}`,
    hash: `${id}`.padStart(4, '0') + 'abcdef0123456789',
    created_at: new Date(Date.UTC(2026, 10, 20, 9, id)).toISOString(),
    ...partial,
  }
}

export const mockAuditEvents: AuditEvent[] = [
  event(4, {
    action: 'APPROVED',
    actor_id: 2,
    actor_role: 'line_manager',
    on_behalf_of_id: 5,
    comment: 'Looks fine',
    changes: { status: { old: 'SUBMITTED', new: 'APPROVED' } },
  }),
  event(3, {
    entity_type: 'approval_step',
    entity_id: 7,
    action: 'STEP_APPROVED',
    actor_id: 2,
    actor_role: 'line_manager',
  }),
  event(2, {
    action: 'POLICY_EVALUATED',
    actor_id: null,
    actor_role: 'SYSTEM',
    changes: { policy_outcome: { old: null, new: 'ROUTE_FOR_APPROVAL' } },
  }),
  event(1, {
    entity_type: 'user',
    entity_id: null,
    claim_id: null,
    action: 'LOGIN_FAILED',
    actor_id: null,
    actor_role: 'SYSTEM',
    changes: { username: 'nobody' },
  }),
]

export const auditLogsHandlers: HttpHandler[] = [
  http.get('/api/v1/audit-logs/verify', ({ request }) => {
    const user = userFrom(request)
    if (!user) return apiError(401, 'unauthorized', 'Sign in again.')
    if (user.role !== 'finance_head') return apiError(403, 'forbidden', 'Finance head only.')
    return HttpResponse.json({
      checked: mockAuditEvents.length,
      valid: true,
      unchained_rows: 0,
      first_broken_id: null,
      problem: null,
    })
  }),
  http.get('/api/v1/audit-logs', ({ request }) => {
    const user = userFrom(request)
    if (!user) return apiError(401, 'unauthorized', 'Sign in again.')
    if (!FINANCE.has(user.role)) return apiError(403, 'forbidden', 'Finance only.')
    const q = new URL(request.url).searchParams
    const entityType = q.get('entityType')?.toLowerCase()
    const action = q.get('action')?.toLowerCase()
    const actorId = q.get('actorId')
    const claimId = q.get('claimId')
    const limit = Number(q.get('limit') ?? 50)
    const offset = Number(q.get('offset') ?? 0)
    const rows = mockAuditEvents.filter(
      (e) =>
        (!entityType || e.entity_type.toLowerCase() === entityType) &&
        (!action || e.action.toLowerCase() === action) &&
        (!actorId || String(e.actor_id) === actorId) &&
        (!claimId || String(e.claim_id) === claimId),
    )
    return HttpResponse.json({
      items: rows.slice(offset, offset + limit),
      total: rows.length,
      limit,
      offset,
    })
  }),
]
