import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { ApprovalsQueue } from '@/features/approvals/components/approvals-queue'

export const Route = createFileRoute('/_authed/approvals')({
  head: () => ({ meta: [{ title: 'Approvals · ExpenseFlow' }] }),
  component: ApprovalsPage,
})

function ApprovalsPage() {
  const { user } = Route.useRouteContext()
  const title = user.role === 'finance_auditor' ? 'Audit queue' : 'Approvals'
  return (
    <>
      <PageHeader
        title={title}
        description="Claims waiting on you, oldest first. Filter, review, or approve in bulk."
      />
      <ApprovalsQueue title={title} />
    </>
  )
}
