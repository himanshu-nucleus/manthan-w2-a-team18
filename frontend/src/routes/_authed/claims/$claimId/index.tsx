import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the E5/M3 screen.
export const Route = createFileRoute('/_authed/claims/$claimId/')({
  component: () => <PageHeader title="Claim" description="Coming soon." />,
})
