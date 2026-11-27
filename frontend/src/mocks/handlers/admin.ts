import { http, HttpResponse, type HttpHandler } from 'msw'
import type { PolicyRule, PolicyRuleUpdate, UserCreateInput } from '@/features/admin/api'
import type { User } from '@/features/auth/api'
import { mockUsers } from '../data'

// MSW handlers for the admin screens (tests + VITE_ENABLE_MOCKS=true).
// Rules mirror the seed in backend/db/seed.sql (docs/policy-approvals-api.md).

const SEEDED_AT = '2026-11-01T09:00:00Z'

function rule(
  code: string,
  name: string,
  category: string | null,
  rule_type: string,
  params: Record<string, unknown>,
  outcome_on_breach: string,
  reason_template: string,
): PolicyRule {
  return {
    code,
    name,
    category,
    rule_type,
    params,
    outcome_on_breach,
    active: true,
    reason_template,
    updated_at: SEEDED_AT,
    updated_by: null,
  }
}

export const mockPolicyRules: PolicyRule[] = [
  rule(
    'MEAL_DAILY_LIMIT',
    'Meals up to 1,500 INR per day',
    'meal',
    'DAILY_CATEGORY_LIMIT',
    { limit: '1500' },
    'ROUTE_FOR_APPROVAL',
    'Meal spend {total} INR on {date} exceeds daily limit of {limit} INR',
  ),
  rule(
    'HOTEL_NIGHTLY_LIMIT_T1',
    'Hotel up to 6,000 INR per night in tier-1 cities',
    'hotel',
    'PER_NIGHT_LIMIT',
    { limit: '6000', city_tier: 'tier1' },
    'ROUTE_FOR_APPROVAL',
    'Hotel {per_night} INR per night in {city} exceeds tier-1 limit of {limit} INR',
  ),
  rule(
    'HOTEL_NIGHTLY_LIMIT_OTHER',
    'Hotel up to 4,000 INR per night in other cities',
    'hotel',
    'PER_NIGHT_LIMIT',
    { limit: '4000', city_tier: 'other' },
    'ROUTE_FOR_APPROVAL',
    'Hotel {per_night} INR per night in {city} exceeds limit of {limit} INR for non-tier-1 cities',
  ),
  rule(
    'CAB_TRIP_LIMIT',
    'Local cab up to 2,000 INR per trip',
    'cab',
    'PER_LINE_LIMIT',
    { limit: '2000' },
    'ROUTE_FOR_APPROVAL',
    'Cab fare {amount} INR on {date} exceeds per-trip limit of {limit} INR',
  ),
  rule(
    'RECEIPT_MANDATORY',
    'Receipt mandatory above 500 INR',
    null,
    'RECEIPT_REQUIRED',
    { above: '500' },
    'AUTO_REJECT',
    'Receipt is mandatory above {above} INR; line {line} ({amount} INR) has none',
  ),
  rule(
    'DUPLICATE_LINE',
    'Same vendor, amount and date as an earlier line',
    null,
    'DUPLICATE_LINE',
    {},
    'ROUTE_FOR_APPROVAL',
    'Possible duplicate: same vendor, amount and date as {match}',
  ),
  rule(
    'DUPLICATE_RECEIPT_HASH',
    'Same receipt file as an earlier receipt',
    null,
    'DUPLICATE_RECEIPT_HASH',
    {},
    'AUTO_REJECT',
    'Duplicate receipt: the same file was already used on {match}',
  ),
  rule(
    'WEEKEND_SPEND',
    'Weekend spend flagged for manager attention',
    null,
    'WEEKEND',
    { days: [5, 6] },
    'ROUTE_FOR_APPROVAL',
    'Expense on {weekday} {date} is weekend spend; flagged for manager attention',
  ),
  {
    ...rule(
      'SPLIT_CLAIM',
      'Possible claim splitting to stay under an approval threshold',
      null,
      'SPLIT_CLAIM',
      { window_days: 7, threshold: '25000' },
      'ROUTE_FOR_APPROVAL',
      'Claims submitted in the last {window_days} days total {combined} INR, above {threshold} INR: possible claim splitting',
    ),
    active: false,
  },
]

const adminUsers: User[] = [...mockUsers]

function caller(request: Request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
  return mockUsers.find((u) => `mock-token-${u.id}` === token) ?? null
}

function error(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

const forbidden = () => error(403, 'forbidden', 'Only the finance head can do this.')

export const adminHandlers: HttpHandler[] = [
  http.get('/api/v1/policy-rules', ({ request }) => {
    const me = caller(request)
    if (!me) return error(401, 'not_authenticated', 'Not signed in.')
    const includeInactive =
      new URL(request.url).searchParams.get('include_inactive') === 'true' &&
      me.role === 'finance_head'
    return HttpResponse.json(mockPolicyRules.filter((r) => includeInactive || r.active))
  }),

  http.put('/api/v1/policy-rules/:code', async ({ request, params }) => {
    const me = caller(request)
    if (me?.role !== 'finance_head') return forbidden()
    const index = mockPolicyRules.findIndex((r) => r.code === params.code)
    if (index < 0) return error(404, 'not_found', 'Policy rule not found.')
    const body = (await request.json()) as PolicyRuleUpdate
    const limit = body.params?.limit
    if (limit !== undefined && !(Number(limit) > 0)) {
      return error(422, 'validation_error', 'limit must be a positive amount.')
    }
    const current = mockPolicyRules[index]
    const updated: PolicyRule = {
      ...current,
      name: body.name ?? current.name,
      params: body.params ?? current.params,
      outcome_on_breach: body.outcome_on_breach ?? current.outcome_on_breach,
      active: body.active ?? current.active,
      reason_template: body.reason_template ?? current.reason_template,
      updated_at: new Date().toISOString(),
      updated_by: me.id,
    }
    mockPolicyRules[index] = updated
    return HttpResponse.json(updated)
  }),

  http.get('/api/v1/users', ({ request }) => {
    if (caller(request)?.role !== 'finance_head') return forbidden()
    return HttpResponse.json(adminUsers)
  }),

  http.post('/api/v1/users', async ({ request }) => {
    if (caller(request)?.role !== 'finance_head') return forbidden()
    const body = (await request.json()) as UserCreateInput
    if (adminUsers.some((u) => u.username === body.username)) {
      return error(409, 'username_taken', 'That username is already in use.')
    }
    const created: User = {
      id: Math.max(...adminUsers.map((u) => u.id)) + 1,
      username: body.username,
      full_name: body.full_name,
      email: body.email ?? null,
      role: body.role,
      manager_id: body.manager_id ?? null,
      is_active: true,
      created_at: new Date().toISOString(),
    }
    adminUsers.push(created)
    return HttpResponse.json(created, { status: 201 })
  }),
]
