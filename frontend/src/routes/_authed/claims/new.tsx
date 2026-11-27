import { createFileRoute } from '@tanstack/react-router'
import { PageHeader } from '@/components/app-shell'

// Placeholder - replaced by the N1-N4 screen.
export const Route = createFileRoute('/_authed/claims/new')({
  component: () => <PageHeader title="New claim" description="Coming soon." />,
})
