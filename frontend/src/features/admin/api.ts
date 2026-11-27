import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { userSchema } from '@/features/auth/api'
import { apiRequest } from '@/lib/api'

// Schemas mirror docs/openapi.json.

export const policyRuleSchema = z.object({
  code: z.string(),
  name: z.string(),
  category: z.string().nullable(),
  rule_type: z.string(),
  params: z.record(z.string(), z.unknown()),
  outcome_on_breach: z.string(),
  active: z.boolean(),
  reason_template: z.string(),
  updated_at: z.string(),
  updated_by: z.number().nullable(),
})
export type PolicyRule = z.infer<typeof policyRuleSchema>

export interface PolicyRuleUpdate {
  name?: string | null
  params?: Record<string, unknown> | null
  outcome_on_breach?: 'ROUTE_FOR_APPROVAL' | 'AUTO_REJECT' | null
  active?: boolean | null
  reason_template?: string | null
}

/** `UserCreate`: finance_head creates every role except finance_head. */
export interface UserCreateInput {
  username: string
  full_name: string
  email?: string | null
  role: 'employee' | 'line_manager' | 'finance_auditor'
  password: string
  manager_id?: number | null
}

export const adminKeys = {
  rules: (includeInactive: boolean) => ['policy-rules', { includeInactive }] as const,
  users: ['users'] as const,
}

/** Any logged-in user may list active rules; finance_head may include inactive ones. */
export const policyRulesQuery = (includeInactive = false) =>
  queryOptions({
    queryKey: adminKeys.rules(includeInactive),
    queryFn: () =>
      apiRequest(`/policy-rules${includeInactive ? '?include_inactive=true' : ''}`, {
        schema: z.array(policyRuleSchema),
      }),
  })

export const updatePolicyRule = (code: string, body: PolicyRuleUpdate) =>
  apiRequest(`/policy-rules/${encodeURIComponent(code)}`, {
    method: 'PUT',
    body,
    schema: policyRuleSchema,
  })

/** finance_head only (403 for everyone else). Oldest first. */
export const usersQuery = queryOptions({
  queryKey: adminKeys.users,
  queryFn: () => apiRequest('/users', { schema: z.array(userSchema) }),
})

export const createUser = (body: UserCreateInput) =>
  apiRequest('/users', { method: 'POST', body, schema: userSchema })
