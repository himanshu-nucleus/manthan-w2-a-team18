import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { loadSession } from '@/features/auth/session'

/** Pathless layout: every route under `_authed/` requires a signed-in user. */
export const Route = createFileRoute('/_authed')({
  beforeLoad: async ({ context, location }) => {
    const user = await loadSession(context.queryClient)
    if (!user) throw redirect({ to: '/login', search: { redirect: location.href } })
    return { user }
  },
  component: Outlet,
})
