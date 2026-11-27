import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the audit trail screen.
export const Route = createFileRoute('/_authed/audit-trail')({
  component: () => <PageHeader title="Audit trail" description="Coming soon." />,
})
