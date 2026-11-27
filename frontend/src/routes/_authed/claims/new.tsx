import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { ClaimForm } from '@/features/claims/components/claim-form'

export const Route = createFileRoute('/_authed/claims/new')({
  head: () => ({ meta: [{ title: 'New claim · ExpenseFlow' }] }),
  component: NewClaimPage,
})

function NewClaimPage() {
  return (
    <div className="mx-auto w-full max-w-3xl">
      <PageHeader
        title="New claim"
        description="Add your expenses, save a draft to attach receipts, then submit."
      />
      <ClaimForm />
    </div>
  )
}
