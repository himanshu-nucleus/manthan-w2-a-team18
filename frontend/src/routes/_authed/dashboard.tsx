import { createFileRoute, redirect } from '@tanstack/react-router'
import { roleHome } from '@/features/auth/session'

/** `/dashboard` (and `/`) forward to the signed-in role's landing page. */
export const Route = createFileRoute('/_authed/dashboard')({
  beforeLoad: ({ context }) => {
    throw redirect({ to: roleHome(context.user.role) })
  },
})
