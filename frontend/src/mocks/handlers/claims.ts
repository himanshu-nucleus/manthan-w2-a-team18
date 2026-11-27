import { delay, http, HttpResponse, type HttpHandler } from 'msw'
import type {
  Attachment,
  Claim,
  ClaimLine,
  ClaimLineInput,
  ClaimWriteInput,
} from '@/features/claims/api'
import { mockUsers } from '../data'

// MSW handlers for the claims screens (tests + VITE_ENABLE_MOCKS=true).
// In-memory store with a tiny stand-in for the policy engine:
//   submit needs receipt_number + receipt_id on lines > 500 INR (422 otherwise, like the backend);
//   total > 50,000 → AUTO_REJECT; a hotel line → ROUTE_FOR_APPROVAL;
//   otherwise AUTO_APPROVE.

const EMPLOYEE_ID = 1

function now() {
  return new Date().toISOString()
}

function line(position: number, overrides: Partial<ClaimLine> = {}): ClaimLine {
  return {
    id: position,
    position,
    category: 'meal',
    amount: '450.00',
    expense_date: '2026-11-20',
    vendor: 'Cafe Coffee Day',
    description: null,
    city: null,
    nights: null,
    receipt_number: null,
    receipt_id: null,
    ...overrides,
  }
}

function claim(id: number, overrides: Partial<Claim> = {}): Claim {
  const lines = overrides.lines ?? [line(1)]
  return {
    id,
    employee_id: EMPLOYEE_ID,
    title: `Claim ${id}`,
    currency: 'INR',
    status: 'DRAFT',
    total_amount: sum(lines),
    submitted_at: null,
    policy_outcome: null,
    submission_round: 0,
    version: 1,
    created_at: '2026-11-20T09:00:00Z',
    updated_at: '2026-11-20T09:00:00Z',
    policy_evaluated_at: null,
    created_by: EMPLOYEE_ID,
    updated_by: EMPLOYEE_ID,
    attachments: [],
    ...overrides,
    lines,
  }
}

function sum(lines: { amount: string | null }[]) {
  return lines.reduce((acc, l) => acc + Number(l.amount ?? 0), 0).toFixed(2)
}

function seed(): Claim[] {
  return [
    claim(1, { title: 'Client visit — Pune', status: 'DRAFT' }),
    claim(2, {
      title: 'Bangalore offsite',
      status: 'PENDING_APPROVAL',
      policy_outcome: 'ROUTE_FOR_APPROVAL',
      submitted_at: '2026-11-21T10:00:00Z',
      submission_round: 1,
      lines: [
        line(1, {
          category: 'hotel',
          amount: '9000.00',
          city: 'Bengaluru',
          nights: 2,
          vendor: 'Taj MG Road',
          receipt_number: 'TAJ-881',
        }),
      ],
    }),
    claim(3, {
      title: 'Team lunch',
      status: 'AUTO_APPROVED',
      policy_outcome: 'AUTO_APPROVE',
      submitted_at: '2026-11-18T12:00:00Z',
      submission_round: 1,
    }),
  ]
}

let claims = seed()
let nextClaimId = 100
let nextAttachmentId = 1

/** Restores the seeded fixtures (call from tests that mutate the store). */
export function resetClaimsStore() {
  claims = seed()
  nextClaimId = 100
  nextAttachmentId = 1
}

function currentUser(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `mock-token-${u.id}` === token)
}

function error(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

function toLines(input: ClaimLineInput[] = []): ClaimLine[] {
  return input.map((l, i) => ({
    id: i + 1,
    position: i + 1,
    category: l.category ?? null,
    amount: l.amount === null || l.amount === undefined ? null : Number(l.amount).toFixed(2),
    expense_date: l.expense_date ?? null,
    vendor: l.vendor ?? null,
    description: l.description ?? null,
    city: l.city ?? null,
    nights: l.nights ?? null,
    receipt_number: l.receipt_number ?? null,
    receipt_id: l.receipt_id ?? null,
  }))
}

function missingForSubmit(c: Claim) {
  const fields: { field: string; message: string }[] = []
  const add = (field: string, message: string) => fields.push({ field, message })
  if (c.lines.length === 0) add('lines', 'at least one line is required to submit')
  c.lines.forEach((l, i) => {
    for (const key of ['category', 'amount', 'expense_date', 'vendor'] as const) {
      if (l[key] === null || l[key] === '') add(`lines.${i}.${key}`, 'is required to submit')
    }
    if (l.category === 'hotel') {
      if (!l.city) add(`lines.${i}.city`, 'is required for hotel lines')
      if (!l.nights) add(`lines.${i}.nights`, 'is required for hotel lines')
    }
    if (Number(l.amount) > 500) {
      const msg = 'is required when the amount is above 500 INR'
      if (!l.receipt_number) add(`lines.${i}.receipt_number`, msg)
      if (!l.receipt_id) add(`lines.${i}.receipt_id`, msg)
    }
  })
  return fields
}

function evaluate(c: Claim) {
  const total = Number(c.total_amount)
  const outcome =
    total > 50000
      ? 'AUTO_REJECT'
      : c.lines.some((l) => l.category === 'hotel')
        ? 'ROUTE_FOR_APPROVAL'
        : 'AUTO_APPROVE'
  const status = {
    AUTO_REJECT: 'AUTO_REJECTED',
    ROUTE_FOR_APPROVAL: 'PENDING_APPROVAL',
    AUTO_APPROVE: 'AUTO_APPROVED',
  }[outcome]
  Object.assign(c, {
    policy_outcome: outcome,
    status,
    submitted_at: now(),
    policy_evaluated_at: now(),
    submission_round: c.submission_round + 1,
  })
}

/** Applies a ClaimWrite body; returns an error response or null. */
function applyWrite(c: Claim, body: ClaimWriteInput) {
  if (body.title !== undefined) c.title = body.title ?? null
  if (body.lines !== undefined) c.lines = toLines(body.lines)
  c.total_amount = sum(c.lines)
  c.version += 1
  c.updated_at = now()
  if (body.action === 'submit') {
    const missing = missingForSubmit(c)
    if (missing.length) {
      return HttpResponse.json(
        {
          error: {
            code: 'validation_error',
            message: 'The claim cannot be submitted until these fields are fixed.',
            details: { fields: missing },
          },
        },
        { status: 422 },
      )
    }
    evaluate(c)
  }
  return null
}

const EDITABLE = ['DRAFT', 'CLARIFICATION_REQUESTED']

export const claimsHandlers: HttpHandler[] = [
  http.get('/api/v1/claims', ({ request }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    const limit = Number(url.searchParams.get('limit') ?? 50)
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const visible = claims
      .filter((c) => user.role !== 'employee' || c.employee_id === user.id)
      .filter((c) => !status || c.status === status)
      .sort((a, b) => b.id - a.id)
    return HttpResponse.json({
      items: visible.slice(offset, offset + limit).map(({ lines: _l, attachments: _a, ...s }) => s),
      total: visible.length,
      limit,
      offset,
    })
  }),

  http.get('/api/v1/claims/:id', ({ request, params }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const c = claims.find((x) => x.id === Number(params.id))
    if (!c || (user.role === 'employee' && c.employee_id !== user.id)) {
      return error(404, 'not_found', 'Claim not found.')
    }
    return HttpResponse.json(c)
  }),

  http.post('/api/v1/claims', async ({ request }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const body = (await request.json()) as ClaimWriteInput
    await delay(150)
    const c = claim(nextClaimId++, {
      employee_id: user.id,
      created_by: user.id,
      updated_by: user.id,
      title: null,
      lines: [],
      created_at: now(),
      updated_at: now(),
      version: 0,
    })
    const failure = applyWrite(c, body)
    if (failure) return failure
    claims.push(c)
    return HttpResponse.json(c, { status: 201 })
  }),

  http.put('/api/v1/claims/:id', async ({ request, params }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const c = claims.find((x) => x.id === Number(params.id))
    if (!c) return error(404, 'not_found', 'Claim not found.')
    if (c.employee_id !== user.id) return error(403, 'forbidden', 'Not your claim.')
    if (!EDITABLE.includes(c.status)) {
      return error(409, 'claim_not_editable', 'This claim can no longer be changed.')
    }
    const body = (await request.json()) as ClaimWriteInput
    await delay(150)
    const draft = structuredClone(c)
    const failure = applyWrite(draft, body)
    if (failure) return failure
    Object.assign(c, draft)
    return HttpResponse.json(c)
  }),

  http.post('/api/v1/claims/:id/submit', ({ request, params }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const c = claims.find((x) => x.id === Number(params.id))
    if (!c) return error(404, 'not_found', 'Claim not found.')
    if (!EDITABLE.includes(c.status)) {
      return error(409, 'claim_not_editable', 'This claim can no longer be changed.')
    }
    const failure = applyWrite(c, { action: 'submit' })
    return failure ?? HttpResponse.json(c)
  }),

  http.post('/api/v1/claims/:id/attachments', async ({ request, params }) => {
    const user = currentUser(request)
    if (!user) return error(401, 'not_authenticated', 'Not signed in.')
    const c = claims.find((x) => x.id === Number(params.id))
    if (!c) return error(404, 'not_found', 'Claim not found.')
    if (!EDITABLE.includes(c.status)) {
      return error(409, 'claim_not_editable', 'This claim can no longer be changed.')
    }
    const form = await request.formData()
    const file = form.get('file')
    if (!(file instanceof File) || file.size === 0) {
      return error(422, 'empty_file', 'The uploaded file is empty.')
    }
    const attachment: Attachment = {
      id: nextAttachmentId++,
      claim_id: c.id,
      original_name: file.name,
      content_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
      sha256: '0'.repeat(64),
      uploaded_by: user.id,
      uploaded_at: now(),
    }
    c.attachments.push(attachment)
    return HttpResponse.json(attachment, { status: 201 })
  }),
]
