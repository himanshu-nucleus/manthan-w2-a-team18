import { http, HttpResponse, type HttpHandler } from 'msw'
import type { BatchDetail, EligibleClaim } from '@/features/payouts/api'
import { mockUsers } from '../data'

// MSW handlers for the payouts screens (tests + VITE_ENABLE_MOCKS=true).
// Fixtures are mutable; call resetPayoutsMock() between tests.

const TOKEN_PREFIX = 'mock-token-'
const FINANCE = new Set(['finance_head', 'finance_auditor'])

function userFrom(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `${TOKEN_PREFIX}${u.id}` === token)
}

function apiError(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

function today() {
  return localDay(new Date())
}

function localDay(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function eligible(id: number, name: string, amount: string): EligibleClaim {
  return {
    claim_id: id,
    claim_code: `CLM-${String(id).padStart(6, '0')}`,
    employee_id: 1,
    employee_code: 'EMP0001',
    beneficiary_name: name,
    department: 'Engineering',
    status: 'APPROVED',
    approved_at: new Date().toISOString(),
    amount,
  }
}

let pending: EligibleClaim[] = []
let batches: BatchDetail[] = []

export function resetPayoutsMock() {
  pending = [eligible(201, 'Employee One', '400.00'), eligible(202, 'Employee One', '1234.50')]
  batches = []
}
resetPayoutsMock()

function guard(request: Request) {
  const user = userFrom(request)
  if (!user) return { error: apiError(401, 'unauthorized', 'Sign in again.') }
  if (!FINANCE.has(user.role)) return { error: apiError(403, 'forbidden', 'Finance only.') }
  return { user }
}

function resolveRange(r: {
  range?: string | null
  fromDate?: string | null
  toDate?: string | null
}) {
  const t = today()
  if (r.range === 'TODAY') return { from: t, to: t }
  if (!r.fromDate || !r.toDate) return 'fromDate and toDate are both required unless range=TODAY.'
  if (r.fromDate > r.toDate) return 'fromDate must be on or before toDate.'
  if (r.toDate > t) return `toDate cannot be in the future (today is ${t}).`
  return { from: r.fromDate, to: r.toDate }
}

function inRange(c: EligibleClaim, from: string, to: string) {
  const day = localDay(new Date(c.approved_at))
  return day >= from && day <= to
}

const sum = (cs: { amount: string }[]) => cs.reduce((s, c) => s + Number(c.amount), 0).toFixed(2)

const summary = ({ items: _items, ...b }: BatchDetail) => b

export const payoutsHandlers: HttpHandler[] = [
  http.get('/api/v1/payouts/eligible-claims', ({ request }) => {
    const g = guard(request)
    if (g.error) return g.error
    const p = new URL(request.url).searchParams
    const r = resolveRange({
      range: p.get('range'),
      fromDate: p.get('fromDate'),
      toDate: p.get('toDate'),
    })
    if (typeof r === 'string') return apiError(400, 'invalid_date_range', r)
    const claims = pending.filter((c) => inRange(c, r.from, r.to))
    return HttpResponse.json({
      from_date: r.from,
      to_date: r.to,
      claim_count: claims.length,
      total_amount: sum(claims),
      claims,
    })
  }),

  http.post('/api/v1/payouts/batches', async ({ request }) => {
    const g = guard(request)
    if (g.error) return g.error
    const body = (await request.json()) as Record<string, string | null>
    const r = resolveRange(body)
    if (typeof r === 'string') return apiError(400, 'invalid_date_range', r)
    const claims = pending.filter((c) => inRange(c, r.from, r.to))
    if (claims.length === 0) {
      return apiError(422, 'no_eligible_claims', 'No approved claims in the selected range.')
    }
    const t = today()
    const reference = `PB-${t.replaceAll('-', '')}-${String(batches.length + 1).padStart(3, '0')}`
    const batch: BatchDetail = {
      id: batches.length + 1,
      batch_reference: reference,
      from_date: r.from,
      to_date: r.to,
      value_date: t,
      claim_count: claims.length,
      total_amount: sum(claims),
      currency: 'INR',
      status: 'CREATED',
      file_name: `payout_${reference}.csv`,
      export_count: 0,
      first_exported_at: null,
      created_by: g.user.id,
      created_at: new Date().toISOString(),
      items: claims.map((c, i) => ({
        transaction_reference: `${reference}-${String(i + 1).padStart(4, '0')}`,
        claim_id: c.claim_id,
        claim_code: c.claim_code,
        employee_id: c.employee_id,
        employee_code: c.employee_code,
        beneficiary_name: c.beneficiary_name,
        department: c.department,
        amount: c.amount,
        narration: `Expense reimbursement ${c.claim_code}`,
      })),
    }
    batches = [batch, ...batches]
    pending = pending.filter((c) => !claims.includes(c))
    return HttpResponse.json(summary(batch), { status: 201 })
  }),

  http.get('/api/v1/payouts/batches', ({ request }) => {
    const g = guard(request)
    if (g.error) return g.error
    const p = new URL(request.url).searchParams
    const limit = Number(p.get('limit') ?? 20)
    const offset = Number(p.get('offset') ?? 0)
    return HttpResponse.json({
      items: batches.slice(offset, offset + limit).map(summary),
      total: batches.length,
      limit,
      offset,
    })
  }),

  http.get('/api/v1/payouts/batches/:id', ({ request, params }) => {
    const g = guard(request)
    if (g.error) return g.error
    const batch = batches.find((b) => b.id === Number(params.id))
    if (!batch) return apiError(404, 'not_found', 'Batch not found.')
    return HttpResponse.json(batch)
  }),

  http.get('/api/v1/payouts/batches/:id/export', ({ request, params }) => {
    const g = guard(request)
    if (g.error) return g.error
    const batch = batches.find((b) => b.id === Number(params.id))
    if (!batch) return apiError(404, 'not_found', 'Batch not found.')
    batch.export_count += 1
    batch.status = 'EXPORTED'
    batch.first_exported_at ??= new Date().toISOString()
    const rows = [
      'BatchReference,TransactionReference,ValueDate,EmployeeId,BeneficiaryName,Department,ClaimId,Amount,Currency,Narration',
      ...batch.items.map((i) =>
        [
          batch.batch_reference,
          i.transaction_reference,
          batch.value_date.split('-').reverse().join('-'),
          i.employee_code,
          i.beneficiary_name,
          i.department ?? '',
          i.claim_code,
          i.amount,
          'INR',
          i.narration,
        ].join(','),
      ),
      `TRAILER,${batch.claim_count},${batch.total_amount}`,
    ]
    return new HttpResponse(rows.join('\r\n') + '\r\n', {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename="${batch.file_name}"`,
      },
    })
  }),
]
