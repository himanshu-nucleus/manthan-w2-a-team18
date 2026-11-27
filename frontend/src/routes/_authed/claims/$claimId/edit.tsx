import { WarningCircleIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { ClaimStatusChip } from '@/components/status-chip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { claimQuery, EDITABLE_STATUSES } from '@/features/claims/api'
import { ClaimForm } from '@/features/claims/components/claim-form'
import { errorMessage } from '@/lib/api'
import { claimRef } from '@/lib/format'

export const Route = createFileRoute('/_authed/claims/$claimId/edit')({
  head: () => ({ meta: [{ title: 'Edit claim · ExpenseFlow' }] }),
  component: EditClaimPage,
})

function EditClaimPage() {
  const { claimId } = Route.useParams()
  const id = Number(claimId)
  const { data: claim, isPending, error } = useQuery(claimQuery(id))

  if (isPending) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <PageHeader title="Edit claim" />
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Couldn't load this claim</AlertTitle>
          <AlertDescription>{errorMessage(error)}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const ref = claimRef(claim.id, claim.created_at)
  const header = (
    <PageHeader
      title={claim.title || 'Untitled claim'}
      description={<span className="font-medium text-primary">{ref}</span>}
    >
      <ClaimStatusChip status={claim.status} />
    </PageHeader>
  )

  if (!EDITABLE_STATUSES.includes(claim.status)) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        {header}
        <Alert>
          <WarningCircleIcon />
          <AlertTitle>This claim can't be edited</AlertTitle>
          <AlertDescription>
            Only drafts and claims sent back for clarification can be changed.
          </AlertDescription>
        </Alert>
        <Button
          className="mt-4"
          variant="outline"
          nativeButton={false}
          render={<Link to="/claims/$claimId" params={{ claimId }} />}
        >
          View claim
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      {header}
      <ClaimForm key={claim.id} claim={claim} />
    </div>
  )
}
