import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { approvalStepSchema, claimSummarySchema } from '@/features/claims/api'
import { apiRequest } from '@/lib/api'

// Schemas mirror docs/openapi.json.

export const pendingItemSchema = z.object({
  step: approvalStepSchema,
  claim: claimSummarySchema,
  on_behalf_of_id: z.number().nullable(),
})
export type PendingItem = z.infer<typeof pendingItemSchema>

export const pendingPageSchema = z.object({
  items: z.array(pendingItemSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
})

export const delegationSchema = z.object({
  id: z.number(),
  delegator_id: z.number(),
  delegate_id: z.number(),
  from_date: z.string(),
  to_date: z.string(),
  reason: z.string().nullable(),
  active: z.boolean(),
  created_at: z.string(),
  cancelled_at: z.string().nullable(),
})
export type Delegation = z.infer<typeof delegationSchema>

export const approvalKeys = {
  pending: (params: { limit: number; offset: number }) => ['approvals', 'pending', params] as const,
  delegations: ['delegations', 'me'] as const,
}

/** My queue: steps assigned to me, open to my role, or delegated to me today; oldest first. */
export const pendingQuery = (params: { limit?: number; offset?: number } = {}) => {
  const limit = params.limit ?? 50
  const offset = params.offset ?? 0
  return queryOptions({
    queryKey: approvalKeys.pending({ limit, offset }),
    queryFn: () =>
      apiRequest(`/approvals/pending?limit=${limit}&offset=${offset}`, {
        schema: pendingPageSchema,
      }),
  })
}

export const delegationsQuery = queryOptions({
  queryKey: approvalKeys.delegations,
  queryFn: () => apiRequest('/delegations/me', { schema: z.array(delegationSchema) }),
})

/** Delegate my approvals to someone of the same or higher role for a date range. */
export const createDelegation = (body: {
  delegate_id: number
  from_date: string
  to_date: string
  reason?: string | null
}) => apiRequest('/delegations', { method: 'POST', body, schema: delegationSchema })

export const cancelDelegation = (id: number) =>
  apiRequest(`/delegations/${id}`, { method: 'DELETE', schema: z.unknown() })
