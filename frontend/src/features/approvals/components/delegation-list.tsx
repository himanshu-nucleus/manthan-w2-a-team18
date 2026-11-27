import { WarningCircleIcon } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { StatusChip, type Tone } from '@/components/status-chip'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  approvalKeys,
  cancelDelegation,
  delegationsQuery,
  type Delegation,
} from '@/features/approvals/api'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { todayIso } from './dates'

function delegationState(d: Delegation, today: string): { label: string; tone: Tone } {
  if (d.cancelled_at || !d.active) return { label: 'Cancelled', tone: 'neutral' }
  if (d.to_date < today) return { label: 'Ended', tone: 'neutral' }
  if (d.from_date > today) return { label: 'Scheduled', tone: 'info' }
  return { label: 'Active now', tone: 'success' }
}

export function DelegationList({ currentUserId }: { currentUserId: number }) {
  const queryClient = useQueryClient()
  const query = useQuery(delegationsQuery)
  const today = todayIso()

  const cancel = useMutation({
    mutationFn: (id: number) => cancelDelegation(id),
    onSuccess: () => {
      toast.success('Delegation cancelled')
      void queryClient.invalidateQueries({ queryKey: approvalKeys.delegations })
      void queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  if (query.isPending) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    )
  }
  if (query.isError) {
    return (
      <Alert variant="destructive">
        <WarningCircleIcon />
        <AlertDescription>{errorMessage(query.error)}</AlertDescription>
      </Alert>
    )
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No delegations yet.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Direction</TableHead>
          <TableHead>Dates</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {query.data.map((d) => {
          const given = d.delegator_id === currentUserId
          const state = delegationState(d, today)
          const cancellable = given && d.active && !d.cancelled_at && d.to_date >= today
          return (
            <TableRow key={d.id}>
              <TableCell>
                {given ? `To User #${d.delegate_id}` : `From User #${d.delegator_id}`}
              </TableCell>
              <TableCell className="tabular">
                {formatDate(d.from_date)} – {formatDate(d.to_date)}
              </TableCell>
              <TableCell className="max-w-[240px] truncate text-muted-foreground">
                {d.reason ?? '—'}
              </TableCell>
              <TableCell>
                <StatusChip tone={state.tone} label={state.label} />
              </TableCell>
              <TableCell className="text-right">
                {cancellable && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={cancel.isPending}
                    onClick={() => cancel.mutate(d.id)}
                  >
                    Cancel
                  </Button>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
