import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the M4 screen.
export const Route = createFileRoute('/_authed/delegations')({
  component: () => <PageHeader title="Out of office" description="Coming soon." />,
})
