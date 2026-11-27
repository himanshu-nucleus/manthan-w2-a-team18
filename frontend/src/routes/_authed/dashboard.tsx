import { SignOutIcon } from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { signOut } from '@/features/auth/session'

const ROLE_LABEL = {
  employee: 'Employee',
  line_manager: 'Line manager',
  finance_auditor: 'Finance auditor',
  finance_head: 'Finance head',
} as const

/** Placeholder landing page until the role dashboards (E1, M1, A0, F0) are built. */
export const Route = createFileRoute('/_authed/dashboard')({
  head: () => ({ meta: [{ title: 'Dashboard · ExpenseFlow' }] }),
  component: DashboardPage,
})

function DashboardPage() {
  const { user } = Route.useRouteContext()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const handleSignOut = () => {
    signOut(queryClient)
    void navigate({ to: '/login', replace: true })
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-8 pt-6 pb-10">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-base font-medium">Hi {user.full_name}</p>
          <h1 className="text-gradient-brand w-fit text-display font-medium">
            Welcome to ExpenseFlow
          </h1>
          <p className="text-sm text-muted-foreground">
            Signed in as {user.username} · {ROLE_LABEL[user.role]}
          </p>
        </div>
        <Button variant="outline" onClick={handleSignOut}>
          <SignOutIcon data-icon="inline-start" />
          Sign out
        </Button>
      </div>
    </main>
  )
}
