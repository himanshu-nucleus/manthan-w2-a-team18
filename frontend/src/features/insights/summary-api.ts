import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { apiRequest } from '@/lib/api'

const amount = z.string()

export const dashboardSummarySchema = z.object({
  month: z.string(),
  generated_at: z.string(),
  active_employees: z.number(),
  kpis: z.object({
    claims: z.object({ value: z.number(), previous: z.number() }),
    total_spend: z.object({ value: amount, previous: amount }),
    policy_violations: z.object({
      lines: z.number(),
      total_lines: z.number(),
      rate_percent: z.number(),
      previous_lines: z.number(),
    }),
    approval_time: z.object({
      average_hours: z.number().nullable(),
      previous_average_hours: z.number().nullable(),
      approved_claims: z.number(),
    }),
    ready_for_payout: z.object({ claims: z.number(), amount }),
  }),
  needs_action: z.object({
    my_pending_approvals: z.number(),
    high_value_pending: z.object({
      threshold: amount,
      count: z.number(),
      claims: z.array(
        z.object({
          id: z.number(),
          title: z.string().nullable(),
          employee_id: z.number(),
          employee_name: z.string(),
          total_amount: amount,
        }),
      ),
    }),
  }),
  monthly_spend: z.array(z.object({ month: z.string(), claims: z.number(), amount })),
  spend_by_category: z.array(z.object({ category: z.string(), amount })),
  spend_by_department: z.array(z.object({ department: z.string(), amount })),
  recent_events: z.array(
    z.object({
      id: z.number(),
      created_at: z.string(),
      actor_id: z.number(),
      actor_name: z.string(),
      action: z.string(),
      entity_type: z.string(),
      entity_id: z.number(),
    }),
  ),
})

export type DashboardSummary = z.infer<typeof dashboardSummarySchema>

/** GET /dashboard/summary — finance_auditor / finance_head only. `month` is `YYYY-MM`. */
export const dashboardSummaryQuery = (month?: string) =>
  queryOptions({
    queryKey: ['dashboard', 'summary', month ?? 'current'] as const,
    queryFn: () =>
      apiRequest(`/dashboard/summary${month ? `?month=${month}` : ''}`, {
        schema: dashboardSummarySchema,
      }),
    staleTime: 60_000,
  })
