import { ArrowLeftIcon, PaperclipIcon, PencilSimpleIcon, WarningIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { PageHeader } from '@/components/app-shell'
import { ClaimStatusChip, PolicyOutcomeChip } from '@/components/status-chip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  ActivityLog,
  ApprovalTimeline,
} from '@/features/claims/components/detail/approval-timeline'
import { currentRoundSteps, personLabel } from '@/features/claims/components/detail/utils'
import { CommentsPanel } from '@/features/claims/components/detail/comments-panel'
import { ReceiptViewer } from '@/features/claims/components/detail/receipt-viewer'
import { ReviewActions } from '@/features/claims/components/detail/review-actions'
import {
  type Attachment,
  approvalStepsQuery,
  CATEGORY_LABEL,
  type Claim,
  claimQuery,
  EDITABLE_STATUSES,
  type ExpenseCategory,
  type PolicyFinding,
  policyResultsQuery,
} from '@/features/claims/api'
import { ApiError, errorMessage } from '@/lib/api'
import { formatDate, formatDateTime, formatInr, claimRef } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_authed/claims/$claimId/')({
  component: ClaimDetailPage,
})

function ClaimDetailPage() {
  const { claimId: rawId } = Route.useParams()
  const { user } = Route.useRouteContext()
  const claimId = Number(rawId)
  const valid = Number.isInteger(claimId) && claimId > 0

  const claim = useQuery({ ...claimQuery(claimId), enabled: valid })
  const policy = useQuery({ ...policyResultsQuery(claimId), enabled: valid && claim.isSuccess })
  const steps = useQuery({ ...approvalStepsQuery(claimId), enabled: valid && claim.isSuccess })
  const [viewing, setViewing] = useState<number | null>(null)

  if (!valid || (claim.isError && claim.error instanceof ApiError && claim.error.status === 404)) {
    return <NotFound />
  }
  if (claim.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Couldn't load the claim</AlertTitle>
        <AlertDescription>{errorMessage(claim.error)}</AlertDescription>
      </Alert>
    )
  }
  if (claim.isPending) return <DetailSkeleton />

  const data = claim.data
  const isOwner = data.employee_id === user.id
  const canEdit = isOwner && EDITABLE_STATUSES.includes(data.status)

  const pendingStep = currentRoundSteps(steps.data ?? []).find((s) => s.status === 'PENDING')
  const canReview =
    data.status === 'PENDING_APPROVAL' &&
    !isOwner &&
    pendingStep !== undefined &&
    (pendingStep.approver_role === user.role ||
      pendingStep.assigned_approver_id === user.id ||
      user.role === 'finance_head')

  const viewingAttachment = data.attachments.find((a) => a.id === viewing) ?? null

  return (
    <div className="flex flex-col gap-4">
      <Link
        to="/claims"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeftIcon size={14} /> Back to claims
      </Link>

      <PageHeader
        title={data.title || 'Untitled claim'}
        description={
          <>
            {claimRef(data.id, data.created_at)} ·{' '}
            {personLabel(data.employee_id, user.id, 'Employee')} · {formatInr(data.total_amount)} ·{' '}
            {data.submitted_at ? `Submitted ${formatDateTime(data.submitted_at)}` : 'Not submitted'}
          </>
        }
        actions={
          canEdit && (
            <Link
              to="/claims/$claimId/edit"
              params={{ claimId: String(data.id) }}
              className={buttonVariants({ variant: 'default' })}
            >
              <PencilSimpleIcon /> Edit claim
            </Link>
          )
        }
      >
        <ClaimStatusChip status={data.status} />
        <PolicyOutcomeChip outcome={data.policy_outcome} />
      </PageHeader>

      <div
        className={cn(
          'grid gap-4',
          viewingAttachment
            ? 'lg:grid-cols-[minmax(0,1fr)_420px]'
            : 'lg:grid-cols-[minmax(0,1fr)_340px]',
        )}
      >
        <div className="flex min-w-0 flex-col gap-4">
          {canReview && pendingStep && <ReviewActions claimId={data.id} step={pendingStep} />}
          <ClaimLevelFindings findings={policy.data?.claim_level ?? []} />
          <LinesCard
            claim={data}
            findings={policy.data?.lines ?? []}
            viewing={viewing}
            onView={setViewing}
          />
          <AttachmentsCard attachments={data.attachments} viewing={viewing} onView={setViewing} />
          <CommentsPanel claimId={data.id} userId={user.id} />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          {viewingAttachment && (
            <ReceiptViewer
              key={viewingAttachment.id}
              claimId={data.id}
              attachment={viewingAttachment}
              onClose={() => setViewing(null)}
            />
          )}
          <ApprovalTimeline claimId={data.id} userId={user.id} />
          <ActivityLog claimId={data.id} userId={user.id} />
        </div>
      </div>
    </div>
  )
}

function ClaimLevelFindings({ findings }: { findings: PolicyFinding[] }) {
  const flagged = findings.filter((f) => f.outcome !== 'AUTO_APPROVE' || f.reasons.length > 0)
  if (flagged.length === 0) return null
  const danger = flagged.some((f) => f.outcome === 'AUTO_REJECT')
  return (
    <Alert
      className={cn(
        danger
          ? 'border-danger-border bg-danger text-danger-foreground'
          : 'border-warning-border bg-warning text-warning-foreground',
      )}
    >
      <WarningIcon />
      <AlertTitle>Policy findings for the whole claim</AlertTitle>
      <AlertDescription className="text-current">
        <ul className="list-disc pl-4">
          {flagged.flatMap((f) =>
            (f.reasons.length ? f.reasons : f.rule_codes).map((r) => <li key={r}>{r}</li>),
          )}
        </ul>
      </AlertDescription>
    </Alert>
  )
}

function LinesCard({
  claim,
  findings,
  viewing,
  onView,
}: {
  claim: Claim
  findings: PolicyFinding[]
  viewing: number | null
  onView: (id: number) => void
}) {
  const lines = [...claim.lines].sort((a, b) => a.position - b.position)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Expense lines</CardTitle>
      </CardHeader>
      <CardContent>
        {lines.length === 0 ? (
          <p className="text-sm text-muted-foreground">No expense lines.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Details</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Receipt</TableHead>
                <TableHead>Policy</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => {
                const finding = findings.find((f) => f.line_position === line.position)
                const receipt = claim.attachments.find((a) => a.id === line.receipt_id)
                return (
                  <TableRow
                    key={line.id}
                    data-state={viewing === line.receipt_id ? 'selected' : undefined}
                  >
                    <TableCell>
                      {line.category
                        ? (CATEGORY_LABEL[line.category as ExpenseCategory] ?? line.category)
                        : '—'}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(line.expense_date)}
                    </TableCell>
                    <TableCell className="max-w-64 whitespace-normal">
                      <div className="font-medium">{line.vendor || '—'}</div>
                      {line.description && (
                        <div className="text-xs text-muted-foreground">{line.description}</div>
                      )}
                      {line.category === 'hotel' && (line.city || line.nights) && (
                        <div className="text-xs text-muted-foreground">
                          {line.city ?? '—'} · {line.nights ?? '?'} night
                          {line.nights === 1 ? '' : 's'}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatInr(line.amount)}
                    </TableCell>
                    <TableCell>
                      {line.receipt_id !== null ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onView(line.receipt_id!)}
                          aria-label={`View receipt for line ${line.position}`}
                        >
                          <PaperclipIcon /> {receipt ? 'View' : `#${line.receipt_id}`}
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {line.receipt_number ? `No file (${line.receipt_number})` : 'None'}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="max-w-72 whitespace-normal">
                      {finding ? (
                        <div className="flex flex-col gap-1">
                          <PolicyOutcomeChip outcome={finding.outcome} />
                          {finding.reasons.map((r) => (
                            <span key={r} className="text-xs text-muted-foreground">
                              {r}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function AttachmentsCard({
  attachments,
  viewing,
  onView,
}: {
  attachments: Attachment[]
  viewing: number | null
  onView: (id: number) => void
}) {
  if (attachments.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Attachments</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        {attachments.map((a) => (
          <Button
            key={a.id}
            variant={viewing === a.id ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => onView(a.id)}
          >
            <PaperclipIcon /> {a.original_name}
          </Button>
        ))}
      </CardContent>
    </Card>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-start gap-3 py-12">
      <h1 className="text-h3 font-medium">Claim not found</h1>
      <p className="text-sm text-muted-foreground">
        It may have been deleted, or you don't have access to it.
      </p>
      <Link to="/claims" className={buttonVariants({ variant: 'outline' })}>
        <ArrowLeftIcon /> Back to claims
      </Link>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="h-8 w-80" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  )
}
