import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { auditEventSchema } from '@/features/claims/api'
import { apiRequest } from '@/lib/api'

export const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
})
export type AuditPage = z.infer<typeof auditPageSchema>

export const chainReportSchema = z.object({
  checked: z.number(),
  valid: z.boolean(),
  unchained_rows: z.number(),
  first_broken_id: z.number().nullable(),
  problem: z.string().nullable(),
})
export type ChainReport = z.infer<typeof chainReportSchema>

export interface AuditFilters {
  entityType?: string
  action?: string
  actorId?: string
  claimId?: string
  fromDate?: string
  toDate?: string
}

export const AUDIT_ENTITY_TYPES = [
  'claim',
  'approval_step',
  'claim_attachment',
  'claim_comment',
  'delegation',
  'policy_rule',
  'policy_setting',
  'payout_batch',
  'user',
  'endpoint',
] as const

export const AUDIT_ACTIONS = [
  'CREATED',
  'UPDATED',
  'SUBMITTED',
  'RESUBMITTED',
  'POLICY_EVALUATED',
  'CHAIN_BUILT',
  'ATTACHMENT_UPLOADED',
  'ATTACHMENT_DOWNLOADED',
  'STEP_APPROVED',
  'APPROVED',
  'REJECTED',
  'SENT_BACK',
  'COMMENTED',
  'DELEGATED',
  'DELEGATION_REVOKED',
  'RULE_CREATED',
  'RULE_UPDATED',
  'SETTING_CREATED',
  'BATCH_CREATED',
  'CSV_EXPORTED',
  'MARKED_PAID',
  'USER_CREATED',
  'LOGIN_FAILED',
  'ACCESS_DENIED',
] as const

export const auditKeys = {
  all: ['audit-logs'] as const,
  search: (f: AuditFilters, limit: number, offset: number) =>
    [...auditKeys.all, f, limit, offset] as const,
}

export function auditSearchParams(f: AuditFilters, limit: number, offset: number) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(f)) {
    const v = value?.trim()
    if (v) params.set(key, v)
  }
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return params
}

export const auditLogsQuery = (f: AuditFilters, limit: number, offset: number) =>
  queryOptions({
    queryKey: auditKeys.search(f, limit, offset),
    queryFn: () =>
      apiRequest(`/audit-logs?${auditSearchParams(f, limit, offset).toString()}`, {
        schema: auditPageSchema,
      }),
  })

export function verifyAuditChain() {
  return apiRequest('/audit-logs/verify', { schema: chainReportSchema })
}

/** `STEP_APPROVED` -> `Step approved`. */
export function humanizeAction(action: string) {
  const s = action.toLowerCase().replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}
