import { InfoIcon } from '@phosphor-icons/react'
import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DelegationForm } from '@/features/approvals/components/delegation-form'
import { DelegationList } from '@/features/approvals/components/delegation-list'

export const Route = createFileRoute('/_authed/delegations')({
  head: () => ({ meta: [{ title: 'Out of office · ExpenseFlow' }] }),
  component: DelegationsPage,
})

function DelegationsPage() {
  const { user } = Route.useRouteContext()
  const canDelegate = user.role !== 'employee'

  return (
    <>
      <PageHeader
        title="Out of office"
        description="Hand your approvals to a colleague while you are away."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>New delegation</CardTitle>
          </CardHeader>
          <CardContent>
            {canDelegate ? (
              <DelegationForm currentUserId={user.id} />
            ) : (
              <Alert>
                <InfoIcon />
                <AlertDescription>
                  Only approvers (line managers and finance) can delegate their approvals.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>My delegations</CardTitle>
          </CardHeader>
          <CardContent>
            <DelegationList currentUserId={user.id} />
          </CardContent>
        </Card>
      </div>
    </>
  )
}
