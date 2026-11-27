import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'
import { AuthBrandPanel } from '@/features/auth/components/auth-brand-panel'
import { LoginForm } from '@/features/auth/components/login-form'
import { loadSession, roleHome, safeRedirect } from '@/features/auth/session'

export const Route = createFileRoute('/login')({
  validateSearch: z.object({ redirect: z.string().optional() }),
  beforeLoad: async ({ context, search }) => {
    const user = await loadSession(context.queryClient)
    if (user) throw redirect({ to: safeRedirect(search.redirect) ?? roleHome(user.role) })
  },
  head: () => ({ meta: [{ title: 'Sign in · ExpenseFlow' }] }),
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const { redirect: redirectTo } = Route.useSearch()

  return (
    <div className="flex min-h-svh gap-4 bg-background p-4">
      <AuthBrandPanel />
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <LoginForm
          onSuccess={(user) =>
            navigate({ to: safeRedirect(redirectTo) ?? roleHome(user.role), replace: true })
          }
        />
      </main>
    </div>
  )
}
