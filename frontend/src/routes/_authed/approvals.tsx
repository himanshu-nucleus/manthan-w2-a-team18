import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the M2/A1 screen.
export const Route = createFileRoute('/_authed/approvals')({
  component: () => <PageHeader title="Approvals" description="Coming soon." />,
})
