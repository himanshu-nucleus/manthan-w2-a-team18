import { PlusIcon, ReceiptIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { z } from 'zod'
import { PageHeader } from '@/components/app-shell'
import { CLAIM_STATUS } from '@/components/status-chip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CLAIM_STATUSES, claimsListQuery } from '@/features/claims/api'
import { ClaimsTable, ClaimsTableSkeleton } from '@/features/claims/components/claims-table'
import { errorMessage } from '@/lib/api'

export const Route = createFileRoute('/_authed/claims/')({
  validateSearch: z.object({ status: z.enum(CLAIM_STATUSES).optional() }),
  head: () => ({ meta: [{ title: 'Claims · ExpenseFlow' }] }),
  component: ClaimsPage,
})

const FILTERS = ['all', ...CLAIM_STATUSES] as const

function ClaimsPage() {
  const { user } = Route.useRouteContext()
  const { status } = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data, isPending, error } = useQuery(claimsListQuery({ status }))
  const isEmployee = user.role === 'employee'
  const title = isEmployee ? 'My claims' : 'All claims'

  const newClaim = (
    <Button nativeButton={false} render={<Link to="/claims/new" />}>
      <PlusIcon data-icon="inline-start" />
      New claim
    </Button>
  )

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={title}
        description={
          isEmployee ? 'Track your expense claims.' : 'Every expense claim across the company.'
        }
        actions={newClaim}
      />

      <div className="-mx-1 overflow-x-auto px-1">
        <Tabs
          value={status ?? 'all'}
          onValueChange={(value) =>
            void navigate({
              search: { status: value === 'all' ? undefined : (value as typeof status) },
            })
          }
        >
          <TabsList>
            {FILTERS.map((f) => (
              <TabsTrigger key={f} value={f}>
                {f === 'all' ? 'All' : (CLAIM_STATUS[f]?.label ?? f)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {isPending ? (
        <ClaimsTableSkeleton />
      ) : error ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Couldn't load claims</AlertTitle>
          <AlertDescription>{errorMessage(error)}</AlertDescription>
        </Alert>
      ) : data.items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center">
          <ReceiptIcon size={32} className="text-muted-foreground" aria-hidden />
          <p className="font-medium">{status ? 'No claims with this status' : 'No claims yet'}</p>
          <p className="text-sm text-muted-foreground">
            {status ? 'Try another filter.' : 'Start a new claim to get your expenses reimbursed.'}
          </p>
          {!status && newClaim}
        </div>
      ) : (
        <ClaimsTable claims={data.items} />
      )}
    </div>
  )
}
