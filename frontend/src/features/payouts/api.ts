import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { apiBlob, apiRequest } from '@/lib/api'

export const eligibleClaimSchema = z.object({
  claim_id: z.number(),
  claim_code: z.string(),
  employee_id: z.number(),
  employee_code: z.string(),
  beneficiary_name: z.string(),
  department: z.string().nullable(),
  status: z.string(),
  approved_at: z.string(),
  amount: z.string(),
})
export type EligibleClaim = z.infer<typeof eligibleClaimSchema>

export const eligiblePreviewSchema = z.object({
  from_date: z.string(),
  to_date: z.string(),
  claim_count: z.number(),
  total_amount: z.string(),
  claims: z.array(eligibleClaimSchema),
})
export type EligiblePreview = z.infer<typeof eligiblePreviewSchema>

export const batchSummarySchema = z.object({
  id: z.number(),
  batch_reference: z.string(),
  from_date: z.string(),
  to_date: z.string(),
  value_date: z.string(),
  claim_count: z.number(),
  total_amount: z.string(),
  currency: z.string(),
  status: z.string(),
  file_name: z.string(),
  export_count: z.number(),
  first_exported_at: z.string().nullable(),
  created_by: z.number(),
  created_at: z.string(),
})
export type BatchSummary = z.infer<typeof batchSummarySchema>

export const batchItemSchema = z.object({
  transaction_reference: z.string(),
  claim_id: z.number(),
  claim_code: z.string(),
  employee_id: z.number(),
  employee_code: z.string(),
  beneficiary_name: z.string(),
  department: z.string().nullable(),
  amount: z.string(),
  narration: z.string(),
})
export type BatchItem = z.infer<typeof batchItemSchema>

export const batchDetailSchema = batchSummarySchema.extend({ items: z.array(batchItemSchema) })
export type BatchDetail = z.infer<typeof batchDetailSchema>

export const batchPageSchema = z.object({
  items: z.array(batchSummarySchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
})

/** `{ range: 'TODAY' }` or an inclusive `YYYY-MM-DD` approval-date range. */
export type PayoutRange = { range: 'TODAY' } | { fromDate: string; toDate: string }

export const payoutKeys = {
  all: ['payouts'] as const,
  eligible: (r: PayoutRange) => ['payouts', 'eligible', r] as const,
  batches: (p: { limit: number; offset: number }) => ['payouts', 'batches', p] as const,
  batch: (id: number) => ['payouts', 'batch', id] as const,
}

function rangeQuery(r: PayoutRange) {
  const params =
    'range' in r
      ? new URLSearchParams({ range: 'TODAY' })
      : new URLSearchParams({ fromDate: r.fromDate, toDate: r.toDate })
  return params.toString()
}

export const eligibleQuery = (r: PayoutRange) =>
  queryOptions({
    queryKey: payoutKeys.eligible(r),
    queryFn: () =>
      apiRequest(`/payouts/eligible-claims?${rangeQuery(r)}`, { schema: eligiblePreviewSchema }),
  })

export const batchesQuery = (p: { limit: number; offset: number } = { limit: 20, offset: 0 }) =>
  queryOptions({
    queryKey: payoutKeys.batches(p),
    queryFn: () =>
      apiRequest(`/payouts/batches?limit=${p.limit}&offset=${p.offset}`, {
        schema: batchPageSchema,
      }),
  })

export const batchQuery = (id: number) =>
  queryOptions({
    queryKey: payoutKeys.batch(id),
    queryFn: () => apiRequest(`/payouts/batches/${id}`, { schema: batchDetailSchema }),
  })

export const createBatch = (r: PayoutRange) =>
  apiRequest('/payouts/batches', { method: 'POST', body: r, schema: batchSummarySchema })

/** Downloads the batch CSV via a temporary `<a download>`. */
export async function downloadBatchCsv(batch: Pick<BatchSummary, 'id' | 'file_name'>) {
  const blob = await apiBlob(`/payouts/batches/${batch.id}/export`)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = batch.file_name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
