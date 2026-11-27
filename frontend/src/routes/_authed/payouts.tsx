import { LockIcon } from '@phosphor-icons/react'
import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { Card } from '@/components/ui/card'
import { PayoutsScreen } from '@/features/payouts/components/payouts-screen'

export const Route = createFileRoute('/_authed/payouts')({
  head: () => ({ meta: [{ title: 'Payouts · ExpenseFlow' }] }),
  component: PayoutsPage,
})

function PayoutsPage() {
  const { user } = Route.useRouteContext()
  const isFinance = user.role === 'finance_head' || user.role === 'finance_auditor'
  return (
    <>
      <PageHeader
        title="Payout batches"
        description="Batch approved claims by approval date, mark them paid, and download the bank CSV."
      />
      {isFinance ? (
        <PayoutsScreen />
      ) : (
        <Card className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <LockIcon size={32} className="text-muted-foreground" />
          <p className="font-medium">Only finance can run payouts</p>
        </Card>
      )}
    </>
  )
}
