import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the E3/E4 screen.
export const Route = createFileRoute('/_authed/claims/$claimId/edit')({
  component: () => <PageHeader title="Edit claim" description="Coming soon." />,
})
