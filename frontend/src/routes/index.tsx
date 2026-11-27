import { createFileRoute, redirect } from '@tanstack/react-router'

// `/` has no page of its own: the dashboard guard sends signed-out users to /login.
export const Route = createFileRoute('/')({
  beforeLoad: () => {
    throw redirect({ to: '/dashboard' })
  },
})
