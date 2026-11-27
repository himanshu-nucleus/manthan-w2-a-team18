import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the F3 screen.
export const Route = createFileRoute('/_authed/admin/policy-rules')({
  component: () => <PageHeader title="Policy rules" description="Coming soon." />,
})
