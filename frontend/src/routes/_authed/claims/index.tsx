import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the E2 screen.
export const Route = createFileRoute('/_authed/claims/')({
  component: () => <PageHeader title="My claims" description="Coming soon." />,
})
