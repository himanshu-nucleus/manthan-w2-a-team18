import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { apiBlob, apiRequest } from '@/lib/api'

// Schemas mirror docs/openapi.json (it wins over the markdown docs on conflict).
// Amounts are decimal strings ("2500.00"); format them with formatInr.

export const CLAIM_STATUSES = [
  'DRAFT',
  'SUBMITTED',
  'AUTO_APPROVED',
  'AUTO_REJECTED',
  'PENDING_APPROVAL',
  'APPROVED',
  'REJECTED',
  'CLARIFICATION_REQUESTED',
  'DUPLICATE',
  'PAID',
] as const
export type ClaimStatus = (typeof CLAIM_STATUSES)[number]

/** Statuses in which the owner may PUT / upload receipts; anything else is 409. */
export const EDITABLE_STATUSES: readonly string[] = ['DRAFT', 'CLARIFICATION_REQUESTED']

export const EXPENSE_CATEGORIES = ['meal', 'hotel', 'local', 'cab', 'airfare', 'other'] as const
export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number]
export const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  meal: 'Meals',
  hotel: 'Hotel',
  local: 'Local travel',
  cab: 'Local cab',
  airfare: 'Airfare',
  other: 'Other',
}

const dateTime = z.string()

export const attachmentSchema = z.object({
  id: z.number(),
  claim_id: z.number(),
  original_name: z.string(),
  content_type: z.string(),
  size_bytes: z.number(),
  sha256: z.string(),
  uploaded_by: z.number(),
  uploaded_at: dateTime,
})
export type Attachment = z.infer<typeof attachmentSchema>

export const claimLineSchema = z.object({
  id: z.number(),
  position: z.number(),
  category: z.string().nullable(),
  amount: z.string().nullable(),
  expense_date: z.string().nullable(),
  vendor: z.string().nullable(),
  description: z.string().nullable(),
  city: z.string().nullable(),
  nights: z.number().nullable(),
  receipt_number: z.string().nullable(),
  receipt_id: z.number().nullable(),
})
export type ClaimLine = z.infer<typeof claimLineSchema>

export const claimSummarySchema = z.object({
  id: z.number(),
  employee_id: z.number(),
  title: z.string().nullable(),
  currency: z.string(),
  status: z.string(),
  total_amount: z.string(),
  submitted_at: dateTime.nullable(),
  policy_outcome: z.string().nullable(),
  approved_at: dateTime.nullable().optional(),
  paid_at: dateTime.nullable().optional(),
  payout_batch_reference: z.string().nullable().optional(),
  submission_round: z.number(),
  version: z.number(),
  created_at: dateTime,
  updated_at: dateTime,
})
export type ClaimSummary = z.infer<typeof claimSummarySchema>

export const claimSchema = claimSummarySchema.extend({
  policy_evaluated_at: dateTime.nullable(),
  created_by: z.number(),
  updated_by: z.number(),
  lines: z.array(claimLineSchema),
  attachments: z.array(attachmentSchema),
})
export type Claim = z.infer<typeof claimSchema>

export const claimPageSchema = z.object({
  items: z.array(claimSummarySchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
})
export type ClaimPage = z.infer<typeof claimPageSchema>

/** `ClaimLineIn`. Hotel lines need `city` and `nights`. */
export interface ClaimLineInput {
  category?: ExpenseCategory | null
  amount?: string | number | null
  expense_date?: string | null
  vendor?: string | null
  description?: string | null
  city?: string | null
  nights?: number | null
  receipt_number?: string | null
  receipt_id?: number | null
}

/** `ClaimWrite`. `action: "submit"` runs the policy engine immediately. */
export interface ClaimWriteInput {
  action?: 'draft' | 'submit'
  title?: string | null
  currency?: string
  lines?: ClaimLineInput[]
}

export const policyFindingSchema = z.object({
  line_position: z.number().nullable(),
  outcome: z.string(),
  rule_codes: z.array(z.string()),
  reasons: z.array(z.string()),
  rule_snapshot: z.record(z.string(), z.unknown()),
  evaluated_at: dateTime,
})
export type PolicyFinding = z.infer<typeof policyFindingSchema>

export const policyResultsSchema = z.object({
  claim_id: z.number(),
  round: z.number(),
  outcome: z.string().nullable(),
  evaluated_at: dateTime.nullable(),
  lines: z.array(policyFindingSchema),
  claim_level: z.array(policyFindingSchema),
})
export type PolicyResults = z.infer<typeof policyResultsSchema>

export const auditEventSchema = z.object({
  id: z.number(),
  entity_type: z.string(),
  entity_id: z.number().nullable(),
  claim_id: z.number().nullable().optional(),
  action: z.string(),
  changes: z.record(z.string(), z.unknown()),
  actor_id: z.number().nullable(),
  actor_role: z.string().nullable().optional(),
  on_behalf_of_id: z.number().nullable().optional(),
  comment: z.string().nullable().optional(),
  ip_address: z.string().nullable().optional(),
  request_id: z.string().nullable().optional(),
  hash: z.string().nullable().optional(),
  created_at: dateTime,
})
export type AuditEvent = z.infer<typeof auditEventSchema>

export const approvalStepSchema = z.object({
  id: z.number(),
  claim_id: z.number(),
  round: z.number(),
  step_order: z.number(),
  approver_role: z.string(),
  assigned_approver_id: z.number().nullable(),
  status: z.string(),
  acted_by_id: z.number().nullable(),
  on_behalf_of_id: z.number().nullable(),
  acted_at: dateTime.nullable(),
  comment: z.string().nullable(),
  created_at: dateTime,
})
export type ApprovalStep = z.infer<typeof approvalStepSchema>

export const commentSchema = z.object({
  id: z.number(),
  claim_id: z.number(),
  author_id: z.number(),
  body: z.string(),
  created_at: dateTime,
})
export type Comment = z.infer<typeof commentSchema>

// ---------------------------------------------------------------- query keys & options

export const claimKeys = {
  all: ['claims'] as const,
  list: (params: { status?: string; limit?: number; offset?: number }) =>
    ['claims', 'list', params] as const,
  detail: (id: number) => ['claims', 'detail', id] as const,
  policyResults: (id: number) => ['claims', 'detail', id, 'policy-results'] as const,
  audit: (id: number) => ['claims', 'detail', id, 'audit'] as const,
  steps: (id: number) => ['claims', 'detail', id, 'approval-steps'] as const,
  comments: (id: number) => ['claims', 'detail', id, 'comments'] as const,
}

export function claimsListQuery(params: { status?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  search.set('limit', String(params.limit ?? 50))
  search.set('offset', String(params.offset ?? 0))
  return queryOptions({
    queryKey: claimKeys.list(params),
    queryFn: () => apiRequest(`/claims?${search}`, { schema: claimPageSchema }),
  })
}

export const claimQuery = (id: number) =>
  queryOptions({
    queryKey: claimKeys.detail(id),
    queryFn: () => apiRequest(`/claims/${id}`, { schema: claimSchema }),
  })

export const policyResultsQuery = (id: number) =>
  queryOptions({
    queryKey: claimKeys.policyResults(id),
    queryFn: () => apiRequest(`/claims/${id}/policy-results`, { schema: policyResultsSchema }),
  })

export const auditQuery = (id: number) =>
  queryOptions({
    queryKey: claimKeys.audit(id),
    queryFn: () => apiRequest(`/claims/${id}/audit`, { schema: z.array(auditEventSchema) }),
  })

export const approvalStepsQuery = (id: number) =>
  queryOptions({
    queryKey: claimKeys.steps(id),
    queryFn: () =>
      apiRequest(`/claims/${id}/approval-steps`, { schema: z.array(approvalStepSchema) }),
  })

export const commentsQuery = (id: number) =>
  queryOptions({
    queryKey: claimKeys.comments(id),
    queryFn: () => apiRequest(`/claims/${id}/comments`, { schema: z.array(commentSchema) }),
  })

// ---------------------------------------------------------------- mutations (plain functions)

export const createClaim = (body: ClaimWriteInput) =>
  apiRequest('/claims', { method: 'POST', body, schema: claimSchema })

export const updateClaim = (id: number, body: ClaimWriteInput) =>
  apiRequest(`/claims/${id}`, { method: 'PUT', body, schema: claimSchema })

export const submitClaim = (id: number) =>
  apiRequest(`/claims/${id}/submit`, { method: 'POST', schema: claimSchema })

export function uploadAttachment(claimId: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiRequest(`/claims/${claimId}/attachments`, {
    method: 'POST',
    body,
    schema: attachmentSchema,
  })
}

/** Receipt bytes (needs the bearer token, so it can't be a plain <img src>). */
export const downloadAttachment = (claimId: number, attachmentId: number) =>
  apiBlob(`/claims/${claimId}/attachments/${attachmentId}`)

export const approveClaim = (id: number, body: { step_id?: number; comment?: string } = {}) =>
  apiRequest(`/claims/${id}/approve`, { method: 'POST', body, schema: claimSchema })

/** Final. `comment` is required. */
export const rejectClaim = (id: number, body: { step_id?: number; comment: string }) =>
  apiRequest(`/claims/${id}/reject`, { method: 'POST', body, schema: claimSchema })

/** Back to the claimant as CLARIFICATION_REQUESTED. `comment` is required. */
export const sendBackClaim = (id: number, body: { step_id?: number; comment: string }) =>
  apiRequest(`/claims/${id}/send-back`, { method: 'POST', body, schema: claimSchema })

export const addComment = (id: number, body: string) =>
  apiRequest(`/claims/${id}/comments`, { method: 'POST', body: { body }, schema: commentSchema })
