import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { usersQueryOptions } from '@/features/users/api'

export const Route = createFileRoute('/users')({
  loader: ({ context }) => context.queryClient.ensureQueryData(usersQueryOptions),
  pendingComponent: () => <p className="p-6 text-muted-foreground">Loading users…</p>,
  errorComponent: ({ error }) => (
    <p role="alert" className="p-6 text-destructive">
      {error instanceof Error ? error.message : 'Something went wrong'}
    </p>
  ),
  component: UsersPage,
})

function UsersPage() {
  const { data: users } = useSuspenseQuery(usersQueryOptions)

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Users</h1>
      <ul className="grid gap-3 sm:grid-cols-2">
        {users.map((user) => (
          <li key={user.id} className="flex items-center gap-3 rounded-lg border p-3">
            <img src={user.avatar} alt="" className="size-10 rounded-full bg-muted" />
            <div className="min-w-0">
              <p className="truncate font-medium">{user.name}</p>
              <p className="truncate text-sm text-muted-foreground">{user.jobTitle}</p>
            </div>
          </li>
        ))}
      </ul>
    </main>
  )
}
