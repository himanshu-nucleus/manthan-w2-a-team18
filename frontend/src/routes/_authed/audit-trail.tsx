import { LockIcon } from '@phosphor-icons/react'
import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'
import { Card } from '@/components/ui/card'
import { AuditTrail, VerifyChainButton } from '@/features/audit/components/audit-trail'

export const Route = createFileRoute('/_authed/audit-trail')({
  head: () => ({ meta: [{ title: 'Audit trail · ExpenseFlow' }] }),
  component: AuditTrailPage,
})

function AuditTrailPage() {
  const { user } = Route.useRouteContext()
  const isFinance = user.role === 'finance_head' || user.role === 'finance_auditor'
  return (
    <>
      <PageHeader
        title="Audit trail"
        description="Every action on claims, approvals, policies and payouts, newest first."
        actions={user.role === 'finance_head' ? <VerifyChainButton /> : undefined}
      />
      {isFinance ? (
        <AuditTrail />
      ) : (
        <Card className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <LockIcon size={32} className="text-muted-foreground" />
          <p className="font-medium">Only finance can view the audit trail</p>
        </Card>
      )}
    </>
  )
}
