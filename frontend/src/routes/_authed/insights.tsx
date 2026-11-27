import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by its screen.
export const Route = createFileRoute('/_authed/insights')({
  component: () => <PageHeader title="Dashboard" description="Coming soon." />,
})
