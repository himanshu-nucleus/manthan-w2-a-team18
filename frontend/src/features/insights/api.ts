import { queryOptions } from '@tanstack/react-query'
import { claimPageSchema, type ClaimSummary } from '@/features/claims/api'
import { apiRequest } from '@/lib/api'

const PAGE = 100
const CAP = 2000

/** Page through GET /claims until `total` (capped). Non-employee roles see every claim. */
export async function fetchAllClaims(): Promise<{ items: ClaimSummary[]; total: number }> {
  const items: ClaimSummary[] = []
  let total = 0
  for (let offset = 0; offset < CAP; offset += PAGE) {
    const page = await apiRequest(`/claims?limit=${PAGE}&offset=${offset}`, {
      schema: claimPageSchema,
    })
    total = page.total
    items.push(...page.items)
    if (page.items.length < PAGE || items.length >= total) break
  }
  return { items, total }
}

export const allClaimsQuery = () =>
  queryOptions({
    queryKey: ['claims', 'list', 'all-for-insights'] as const,
    queryFn: fetchAllClaims,
    staleTime: 60_000,
  })
