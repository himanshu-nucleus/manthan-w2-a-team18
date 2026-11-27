import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusChip } from '@/components/status-chip'
import { approvalStepsQuery, auditQuery } from '@/features/claims/api'
import { currentRoundSteps, humanize, personLabel, ROLE_LABEL, STEP_STATUS } from './utils'
import { formatDateTime } from '@/lib/format'

export function ApprovalTimeline({ claimId, userId }: { claimId: number; userId: number }) {
  const stepsQuery = useQuery(approvalStepsQuery(claimId))
  const steps = currentRoundSteps(stepsQuery.data ?? [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Approval chain</CardTitle>
      </CardHeader>
      <CardContent>
        {stepsQuery.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : stepsQuery.isError ? (
          <p className="text-sm text-muted-foreground">Couldn't load approval steps.</p>
        ) : steps.length === 0 ? (
          <p className="text-sm text-muted-foreground">No approval chain for this claim.</p>
        ) : (
          <ol className="flex flex-col gap-4 border-l pl-4">
            {steps.map((step) => {
              const meta = STEP_STATUS[step.status] ?? {
                label: humanize(step.status),
                tone: 'neutral' as const,
              }
              return (
                <li key={step.id} className="relative flex flex-col gap-1">
                  <span className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border bg-background" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">
                      {ROLE_LABEL[step.approver_role] ?? humanize(step.approver_role)}
                    </span>
                    <StatusChip tone={meta.tone} label={meta.label} />
                  </div>
                  {step.assigned_approver_id !== null && (
                    <span className="text-xs text-muted-foreground">
                      Assigned to {personLabel(step.assigned_approver_id, userId)}
                    </span>
                  )}
                  {step.acted_at && (
                    <span className="text-xs text-muted-foreground">
                      {personLabel(step.acted_by_id, userId)}
                      {step.on_behalf_of_id !== null &&
                        ` on behalf of ${personLabel(step.on_behalf_of_id, userId)}`}{' '}
                      · {formatDateTime(step.acted_at)}
                    </span>
                  )}
                  {step.comment && (
                    <p className="rounded-md bg-muted px-2 py-1 text-sm">“{step.comment}”</p>
                  )}
                </li>
              )
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

export function ActivityLog({ claimId, userId }: { claimId: number; userId: number }) {
  const audit = useQuery(auditQuery(claimId))
  const events = [...(audit.data ?? [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime() || b.id - a.id,
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {audit.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : audit.isError ? (
          <p className="text-sm text-muted-foreground">Couldn't load activity.</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {events.map((event) => (
              <li key={event.id} className="flex flex-col text-sm">
                <span>
                  <span className="font-medium">{humanize(event.action)}</span>
                  <span className="text-muted-foreground">
                    {' '}
                    by {personLabel(event.actor_id, userId)}
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(event.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
