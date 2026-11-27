import { Link, useNavigate } from '@tanstack/react-router'
import { ClaimStatusChip, PolicyOutcomeChip } from '@/components/status-chip'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ClaimSummary } from '@/features/claims/api'
import { claimRef, formatDate, formatInr } from '@/lib/format'

/** E2 claims table. Rows open the claim detail page. */
export function ClaimsTable({ claims }: { claims: ClaimSummary[] }) {
  const navigate = useNavigate()
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Claim</TableHead>
            <TableHead className="hidden md:table-cell">Title</TableHead>
            <TableHead className="hidden sm:table-cell">Date</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="hidden lg:table-cell">Policy</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {claims.map((c) => (
            <TableRow
              key={c.id}
              className="cursor-pointer"
              onClick={() =>
                void navigate({ to: '/claims/$claimId', params: { claimId: String(c.id) } })
              }
            >
              <TableCell>
                <Link
                  to="/claims/$claimId"
                  params={{ claimId: String(c.id) }}
                  className="font-medium text-primary hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {claimRef(c.id, c.created_at)}
                </Link>
                <div className="max-w-[40vw] truncate text-xs text-muted-foreground md:hidden">
                  {c.title || 'Untitled claim'}
                </div>
              </TableCell>
              <TableCell className="hidden max-w-xs truncate md:table-cell">
                {c.title || <span className="text-muted-foreground">Untitled claim</span>}
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                {formatDate(c.submitted_at ?? c.created_at)}
              </TableCell>
              <TableCell className="tabular text-right">{formatInr(c.total_amount)}</TableCell>
              <TableCell>
                <ClaimStatusChip status={c.status} />
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                <PolicyOutcomeChip outcome={c.policy_outcome} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function ClaimsTableSkeleton() {
  return (
    <div className="flex flex-col gap-2 rounded-xl border bg-card p-4" aria-busy="true">
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}
