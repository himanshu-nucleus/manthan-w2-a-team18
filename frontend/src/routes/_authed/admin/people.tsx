import { LockIcon, MagnifyingGlassIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { PageHeader, ROLE_LABEL } from '@/components/app-shell'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { usersQuery } from '@/features/admin/api'
import { AddPersonDialog } from '@/features/admin/components/add-person-dialog'
import { roleSchema } from '@/features/auth/api'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'

export const Route = createFileRoute('/_authed/admin/people')({
  head: () => ({ meta: [{ title: 'People · ExpenseFlow' }] }),
  component: PeoplePage,
})

const ALL_ROLES = 'all'
const ROLE_FILTER_ITEMS = [
  { value: ALL_ROLES, label: 'All roles' },
  ...roleSchema.options.map((role) => ({ value: role, label: ROLE_LABEL[role] })),
]

function PeoplePage() {
  const { user } = Route.useRouteContext()
  if (user.role !== 'finance_head') {
    return (
      <>
        <PageHeader title="People" />
        <Alert>
          <LockIcon />
          <AlertTitle>Only the finance head can manage people</AlertTitle>
          <AlertDescription>Ask your finance head to add or change accounts.</AlertDescription>
        </Alert>
      </>
    )
  }
  return <PeopleDirectory />
}

function PeopleDirectory() {
  const users = useQuery(usersQuery)
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<string>(ALL_ROLES)

  const byId = useMemo(() => new Map((users.data ?? []).map((u) => [u.id, u])), [users.data])
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (users.data ?? []).filter(
      (u) =>
        (role === ALL_ROLES || u.role === role) &&
        (!q ||
          u.full_name.toLowerCase().includes(q) ||
          u.username.toLowerCase().includes(q) ||
          (u.email ?? '').toLowerCase().includes(q)),
    )
  }, [users.data, search, role])

  return (
    <>
      <PageHeader
        title="People"
        description="Everyone who can sign in, their role and who approves their claims."
        actions={<AddPersonDialog users={users.data ?? []} />}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <MagnifyingGlassIcon
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="search"
            aria-label="Search people"
            placeholder="Search name, username or email"
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select items={ROLE_FILTER_ITEMS} value={role} onValueChange={(v) => v && setRole(v)}>
          <SelectTrigger aria-label="Filter by role" className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLE_FILTER_ITEMS.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {users.isError ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertDescription>{errorMessage(users.error)}</AlertDescription>
        </Alert>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Manager</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.isPending
                ? Array.from({ length: 4 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={7}>
                        <Skeleton className="h-5 w-full" />
                      </TableCell>
                    </TableRow>
                  ))
                : filtered.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.full_name}</TableCell>
                      <TableCell className="text-muted-foreground">{u.username}</TableCell>
                      <TableCell className="text-muted-foreground">{u.email ?? '—'}</TableCell>
                      <TableCell>{ROLE_LABEL[u.role]}</TableCell>
                      <TableCell>
                        {u.manager_id
                          ? (byId.get(u.manager_id)?.full_name ?? `#${u.manager_id}`)
                          : '—'}
                      </TableCell>
                      <TableCell>
                        {u.is_active ? (
                          <Badge variant="secondary">Active</Badge>
                        ) : (
                          <Badge variant="outline">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(u.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
              {users.isSuccess && filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                    No people match these filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
