import { CheckCircleIcon, MagnifyingGlassIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { PolicyOutcomeChip } from '@/components/status-chip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { pendingQuery, type PendingItem } from '@/features/approvals/api'
import { approveClaim, claimKeys } from '@/features/claims/api'
import { errorMessage } from '@/lib/api'
import { claimRef, formatAge, formatInr } from '@/lib/format'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

type OutcomeFilter = 'all' | 'AUTO_APPROVE' | 'ROUTE_FOR_APPROVAL'

const OUTCOME_OPTIONS: { value: OutcomeFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'AUTO_APPROVE', label: 'Within policy' },
  { value: 'ROUTE_FOR_APPROVAL', label: 'Needs approval' },
]

const ROLE_LABEL: Record<string, string> = {
  line_manager: 'Line manager',
  finance_auditor: 'Finance auditor',
  finance_head: 'Finance head',
}

interface Filters {
  search: string
  outcome: OutcomeFilter
  minAmount: string
  maxAmount: string
  fromDate: string
  toDate: string
}

const EMPTY_FILTERS: Filters = {
  search: '',
  outcome: 'all',
  minAmount: '',
  maxAmount: '',
  fromDate: '',
  toDate: '',
}

/** Local calendar day `YYYY-MM-DD` of an instant. */
function localDay(value: string) {
  const d = new Date(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function matches(item: PendingItem, f: Filters) {
  const { claim } = item
  const q = f.search.trim().toLowerCase()
  if (q) {
    const ref = claimRef(claim.id, claim.created_at).toLowerCase()
    const title = (claim.title ?? '').toLowerCase()
    if (!ref.includes(q) && !title.includes(q) && String(claim.id) !== q) return false
  }
  if (f.outcome !== 'all' && claim.policy_outcome !== f.outcome) return false
  const amount = Number(claim.total_amount)
  if (f.minAmount !== '' && amount < Number(f.minAmount)) return false
  if (f.maxAmount !== '' && amount > Number(f.maxAmount)) return false
  if (f.fromDate || f.toDate) {
    if (!claim.submitted_at) return false
    const day = localDay(claim.submitted_at)
    if (f.fromDate && day < f.fromDate) return false
    if (f.toDate && day > f.toDate) return false
  }
  return true
}

export function ApprovalsQueue({ title }: { title: string }) {
  const queryClient = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)

  const query = useQuery({
    ...pendingQuery({ limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  })
  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const filtered = useMemo(() => items.filter((i) => matches(i, filters)), [items, filters])
  const selectedItems = items.filter((i) => selected.has(i.step.id))
  const selectedTotal = selectedItems.reduce((sum, i) => sum + Number(i.claim.total_amount), 0)
  const hiddenSelected = selectedItems.filter((i) => !filtered.includes(i)).length

  const allFilteredSelected = filtered.length > 0 && filtered.every((i) => selected.has(i.step.id))
  const someFilteredSelected = filtered.some((i) => selected.has(i.step.id))
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(EMPTY_FILTERS)
  const busy = progress !== null

  const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setFilters((f) => ({ ...f, [key]: value }))

  function toggle(stepId: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(stepId)
      else next.delete(stepId)
      return next
    })
  }

  function toggleAll(checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      for (const i of filtered) {
        if (checked) next.add(i.step.id)
        else next.delete(i.step.id)
      }
      return next
    })
  }

  function goToPage(nextOffset: number) {
    setSelected(new Set())
    setOffset(nextOffset)
  }

  async function approveSelected() {
    const batch = selectedItems
    if (batch.length === 0) return
    const failures: { ref: string; message: string }[] = []
    setProgress({ done: 0, total: batch.length })
    for (const [index, item] of batch.entries()) {
      try {
        await approveClaim(item.claim.id, { step_id: item.step.id })
      } catch (err) {
        failures.push({
          ref: claimRef(item.claim.id, item.claim.created_at),
          message: errorMessage(err),
        })
      }
      setProgress({ done: index + 1, total: batch.length })
    }
    const ok = batch.length - failures.length
    const message = `Approved ${ok} of ${batch.length}`
    if (failures.length === 0) {
      toast.success(message)
    } else {
      toast.error(message, {
        description: failures.map((f) => `${f.ref}: ${f.message}`).join('\n'),
      })
    }
    setProgress(null)
    setSelected(new Set())
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['approvals'] }),
      queryClient.invalidateQueries({ queryKey: claimKeys.all }),
    ])
  }

  const total = query.data?.total ?? 0
  const pageStart = total === 0 ? 0 : offset + 1
  const pageEnd = offset + items.length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {query.isSuccess
            ? filtersActive
              ? `Showing ${filtered.length} of ${items.length} on this page · ${total} waiting in total`
              : `${total} waiting for ${title === 'Audit queue' ? 'audit' : 'your approval'}`
            : ' '}
        </p>
      </div>

      <Card className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-[220px] flex-1 flex-col gap-1.5">
            <Label htmlFor="q-search">Search</Label>
            <div className="relative">
              <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="q-search"
                placeholder="Ref or title"
                className="h-8 pl-8"
                value={filters.search}
                onChange={(e) => setFilter('search', e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Policy</span>
            <div role="group" aria-label="Policy outcome" className="flex gap-1">
              {OUTCOME_OPTIONS.map((o) => (
                <Button
                  key={o.value}
                  type="button"
                  size="sm"
                  variant={filters.outcome === o.value ? 'default' : 'outline'}
                  aria-pressed={filters.outcome === o.value}
                  onClick={() => setFilter('outcome', o.value)}
                >
                  {o.label}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Amount (₹)</span>
            <div className="flex items-center gap-1">
              <Input
                aria-label="Minimum amount"
                type="number"
                min={0}
                placeholder="Min"
                className="h-8 w-24"
                value={filters.minAmount}
                onChange={(e) => setFilter('minAmount', e.target.value)}
              />
              <span className="text-muted-foreground">–</span>
              <Input
                aria-label="Maximum amount"
                type="number"
                min={0}
                placeholder="Max"
                className="h-8 w-24"
                value={filters.maxAmount}
                onChange={(e) => setFilter('maxAmount', e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Submitted</span>
            <div className="flex items-center gap-1">
              <Input
                aria-label="Submitted from"
                type="date"
                className="h-8 w-36"
                value={filters.fromDate}
                onChange={(e) => setFilter('fromDate', e.target.value)}
              />
              <span className="text-muted-foreground">–</span>
              <Input
                aria-label="Submitted to"
                type="date"
                className="h-8 w-36"
                value={filters.toDate}
                onChange={(e) => setFilter('toDate', e.target.value)}
              />
            </div>
          </div>
          {filtersActive && (
            <Button variant="ghost" size="sm" onClick={() => setFilters(EMPTY_FILTERS)}>
              Reset filters
            </Button>
          )}
        </div>
      </Card>

      {selectedItems.length > 0 && (
        <div
          role="region"
          aria-label="Bulk actions"
          className="bg-night flex flex-wrap items-center justify-between gap-3 rounded-[18px] px-5 py-3 text-white"
        >
          <div className="flex flex-col">
            <span className="text-sm font-medium">
              {selectedItems.length} {selectedItems.length === 1 ? 'claim' : 'claims'} selected ·{' '}
              <span className="tabular">{formatInr(selectedTotal)}</span>
            </span>
            {hiddenSelected > 0 && (
              <span className="text-xs text-white/60">
                {hiddenSelected} selected {hiddenSelected === 1 ? 'claim is' : 'claims are'} hidden
                by the current filters
              </span>
            )}
            {progress && (
              <span className="text-xs text-white/75" aria-live="polite">
                Approving {progress.done} of {progress.total}…
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-white hover:bg-white/10 hover:text-white"
              disabled={busy}
              onClick={() => setSelected(new Set())}
            >
              Clear
            </Button>
            <Button variant="secondary" size="sm" disabled={busy} onClick={approveSelected}>
              <CheckCircleIcon />
              Approve {selectedItems.length}
            </Button>
          </div>
        </div>
      )}

      {query.isPending ? (
        <Card className="flex flex-col gap-2 p-4" aria-label="Loading queue">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </Card>
      ) : query.isError ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Couldn't load the queue</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            {errorMessage(query.error)}
            <Button size="sm" variant="outline" onClick={() => query.refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <CheckCircleIcon size={32} className="text-success-foreground" />
          <p className="font-medium">Nothing waiting for you</p>
          <p className="text-sm text-muted-foreground">
            New claims routed to you will show up here.
          </p>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <Table className={cn(query.isFetching && 'opacity-70')}>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 pl-4">
                  <Checkbox
                    aria-label="Select all"
                    checked={allFilteredSelected}
                    indeterminate={someFilteredSelected && !allFilteredSelected}
                    disabled={filtered.length === 0 || busy}
                    onCheckedChange={(checked) => toggleAll(checked)}
                  />
                </TableHead>
                <TableHead>Claim</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Employee</TableHead>
                <TableHead>Step</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead>Age</TableHead>
                <TableHead className="pr-4">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="py-10 text-center text-muted-foreground">
                    No claims match these filters.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((item) => {
                  const { claim, step } = item
                  const ref = claimRef(claim.id, claim.created_at)
                  const isSelected = selected.has(step.id)
                  return (
                    <TableRow key={step.id} data-state={isSelected ? 'selected' : undefined}>
                      <TableCell className="pl-4">
                        <Checkbox
                          aria-label={`Select ${ref}`}
                          checked={isSelected}
                          disabled={busy}
                          onCheckedChange={(checked) => toggle(step.id, checked)}
                        />
                      </TableCell>
                      <TableCell>
                        <Link
                          to="/claims/$claimId"
                          params={{ claimId: String(claim.id) }}
                          className="font-medium text-primary hover:underline"
                        >
                          {ref}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-[260px] truncate">
                        {claim.title ?? 'Untitled claim'}
                      </TableCell>
                      <TableCell>Employee #{claim.employee_id}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span>{ROLE_LABEL[step.approver_role] ?? step.approver_role}</span>
                          {item.on_behalf_of_id !== null && (
                            <span className="text-xs text-muted-foreground">
                              on behalf of User #{item.on_behalf_of_id}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="tabular text-right font-medium">
                        {formatInr(claim.total_amount)}
                      </TableCell>
                      <TableCell>
                        <PolicyOutcomeChip outcome={claim.policy_outcome} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatAge(claim.submitted_at)}
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        <Link
                          to="/claims/$claimId"
                          params={{ claimId: String(claim.id) }}
                          className={buttonVariants({ variant: 'outline', size: 'sm' })}
                        >
                          Review
                        </Link>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </Card>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>
            {pageStart}–{pageEnd} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0 || busy}
              onClick={() => goToPage(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total || busy}
              onClick={() => goToPage(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
