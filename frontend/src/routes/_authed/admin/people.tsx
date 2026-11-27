import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the F4 screen.
export const Route = createFileRoute('/_authed/admin/people')({
  component: () => <PageHeader title="People" description="Coming soon." />,
})
