import {
  CaretDownIcon,
  CaretRightIcon,
  ClockCounterClockwiseIcon,
  LockIcon,
  ShieldCheckIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Fragment, useState, type FormEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
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
import {
  AUDIT_ACTIONS,
  AUDIT_ENTITY_TYPES,
  auditLogsQuery,
  humanizeAction,
  verifyAuditChain,
  type AuditFilters,
} from '@/features/audit/api'
import type { AuditEvent } from '@/features/claims/api'
import { errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

const ROLE_LABEL: Record<string, string> = {
  employee: 'Employee',
  line_manager: 'Line manager',
  finance_auditor: 'Finance auditor',
  finance_head: 'Finance head',
  SYSTEM: 'System',
}

const EMPTY: Required<AuditFilters> = {
  entityType: '',
  action: '',
  actorId: '',
  claimId: '',
  fromDate: '',
  toDate: '',
}

const selectClass =
  'h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

/** Finance head only: recomputes the hash chain server-side and shows the verdict. */
export function VerifyChainButton() {
  const verify = useMutation({ mutationFn: verifyAuditChain })
  const report = verify.data
  return (
    <div className="flex flex-col items-end gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={verify.isPending}
        onClick={() => verify.mutate()}
      >
        <ShieldCheckIcon />
        {verify.isPending ? 'Verifying…' : 'Verify integrity'}
      </Button>
      {verify.isError && (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Couldn't verify</AlertTitle>
          <AlertDescription>{errorMessage(verify.error)}</AlertDescription>
        </Alert>
      )}
      {report &&
        (report.valid ? (
          <Alert className="border-success-foreground/40 text-success-foreground">
            <ShieldCheckIcon />
            <AlertTitle>Chain intact ({report.checked} rows)</AlertTitle>
            {report.unchained_rows > 0 && (
              <AlertDescription>
                {report.unchained_rows} older rows predate the hash chain.
              </AlertDescription>
            )}
          </Alert>
        ) : (
          <Alert variant="destructive">
            <WarningCircleIcon />
            <AlertTitle>Broken at row #{report.first_broken_id ?? '?'}</AlertTitle>
            <AlertDescription>
              {report.problem ?? 'The hash chain does not match.'} Checked {report.checked} rows.
            </AlertDescription>
          </Alert>
        ))}
    </div>
  )
}

function ChangesView({ event }: { event: AuditEvent }) {
  const entries = Object.entries(event.changes)
  return (
    <div className="flex flex-col gap-2 text-xs">
      {entries.length === 0 ? (
        <p className="text-muted-foreground">No field changes recorded.</p>
      ) : (
        <table className="w-full max-w-2xl">
          <tbody>
            {entries.map(([field, value]) => {
              const isDiff =
                value !== null && typeof value === 'object' && ('old' in value || 'new' in value)
              const diff = value as { old?: unknown; new?: unknown }
              return (
                <tr key={field} className="align-top">
                  <td className="py-0.5 pr-3 font-medium">{field}</td>
                  <td className="py-0.5 font-mono break-all">
                    {isDiff ? (
                      <>
                        <span className="text-muted-foreground line-through">
                          {JSON.stringify(diff.old ?? null)}
                        </span>{' '}
                        → <span>{JSON.stringify(diff.new ?? null)}</span>
                      </>
                    ) : (
                      JSON.stringify(value)
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <p className="text-muted-foreground">
        Request {event.request_id ?? '—'} · IP {event.ip_address ?? '—'} · Hash{' '}
        <span className="font-mono break-all">{event.hash ?? '—'}</span>
      </p>
    </div>
  )
}

export function AuditTrail() {
  const [draft, setDraft] = useState<Required<AuditFilters>>(EMPTY)
  const [filters, setFilters] = useState<AuditFilters>({})
  const [offset, setOffset] = useState(0)
  const [expanded, setExpanded] = useState<number | null>(null)

  const query = useQuery({
    ...auditLogsQuery(filters, PAGE_SIZE, offset),
    placeholderData: keepPreviousData,
  })
  const items = query.data?.items ?? []
  const total = query.data?.total ?? 0

  const set = (key: keyof AuditFilters, value: string) => setDraft((d) => ({ ...d, [key]: value }))

  function apply(e: FormEvent) {
    e.preventDefault()
    setFilters({ ...draft })
    setOffset(0)
  }

  function reset() {
    setDraft(EMPTY)
    setFilters({})
    setOffset(0)
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <LockIcon /> Append-only — entries cannot be edited or deleted.
      </p>

      <Card className="p-4">
        <form onSubmit={apply} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="a-entity">Entity type</Label>
            <select
              id="a-entity"
              className={selectClass}
              value={draft.entityType}
              onChange={(e) => set('entityType', e.target.value)}
            >
              <option value="">All</option>
              {AUDIT_ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="a-action">Action</Label>
            <Input
              id="a-action"
              list="a-action-list"
              placeholder="e.g. APPROVED"
              className="h-8 w-44"
              value={draft.action}
              onChange={(e) => set('action', e.target.value)}
            />
            <datalist id="a-action-list">
              {AUDIT_ACTIONS.map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="a-actor">Actor id</Label>
            <Input
              id="a-actor"
              type="number"
              min={1}
              className="h-8 w-24"
              value={draft.actorId}
              onChange={(e) => set('actorId', e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="a-claim">Claim id</Label>
            <Input
              id="a-claim"
              type="number"
              min={1}
              className="h-8 w-24"
              value={draft.claimId}
              onChange={(e) => set('claimId', e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Date</span>
            <div className="flex items-center gap-1">
              <Input
                aria-label="From date"
                type="date"
                className="h-8 w-36"
                value={draft.fromDate}
                onChange={(e) => set('fromDate', e.target.value)}
              />
              <span className="text-muted-foreground">–</span>
              <Input
                aria-label="To date"
                type="date"
                className="h-8 w-36"
                value={draft.toDate}
                onChange={(e) => set('toDate', e.target.value)}
              />
            </div>
          </div>
          <Button type="submit" size="sm">
            Apply
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={reset}>
            Reset
          </Button>
        </form>
      </Card>

      {query.isPending ? (
        <Card className="flex flex-col gap-2 p-4" aria-label="Loading audit trail">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </Card>
      ) : query.isError ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertTitle>Couldn't load the audit trail</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            {errorMessage(query.error)}
            <Button size="sm" variant="outline" onClick={() => query.refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <ClockCounterClockwiseIcon size={32} className="text-muted-foreground" />
          <p className="font-medium">No audit entries match</p>
          <p className="text-sm text-muted-foreground">Try widening the filters.</p>
        </Card>
      ) : (
        <>
          <Card className="overflow-hidden p-0">
            <Table className={cn('text-xs', query.isFetching && 'opacity-70')}>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8 pl-4">
                    <span className="sr-only">Expand</span>
                  </TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>On behalf of</TableHead>
                  <TableHead>Comment</TableHead>
                  <TableHead className="pr-4">Hash</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((ev) => {
                  const open = expanded === ev.id
                  return (
                    <Fragment key={ev.id}>
                      <TableRow data-state={open ? 'selected' : undefined}>
                        <TableCell className="pl-4">
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            aria-label={`${open ? 'Hide' : 'Show'} details for entry ${ev.id}`}
                            aria-expanded={open}
                            onClick={() => setExpanded(open ? null : ev.id)}
                          >
                            {open ? <CaretDownIcon /> : <CaretRightIcon />}
                          </Button>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          {formatDateTime(ev.created_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span>{ev.actor_id === null ? 'System' : `User #${ev.actor_id}`}</span>
                            {ev.actor_role && (
                              <span className="text-muted-foreground">
                                {ROLE_LABEL[ev.actor_role] ?? ev.actor_role}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">{humanizeAction(ev.action)}</TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span>
                              {ev.entity_type}
                              {ev.entity_id !== null && ` #${ev.entity_id}`}
                            </span>
                            {ev.claim_id != null && (
                              <Link
                                to="/claims/$claimId"
                                params={{ claimId: String(ev.claim_id) }}
                                className="text-primary hover:underline"
                              >
                                Claim #{ev.claim_id}
                              </Link>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {ev.on_behalf_of_id != null ? `User #${ev.on_behalf_of_id}` : '—'}
                        </TableCell>
                        <TableCell className="max-w-[220px] truncate" title={ev.comment ?? ''}>
                          {ev.comment ?? '—'}
                        </TableCell>
                        <TableCell className="pr-4 font-mono" title={ev.hash ?? ''}>
                          {ev.hash ? ev.hash.slice(0, 8) : '—'}
                        </TableCell>
                      </TableRow>
                      {open && (
                        <TableRow>
                          <TableCell
                            colSpan={8}
                            className="bg-muted/40 px-4 py-3 whitespace-normal"
                          >
                            <ChangesView event={ev} />
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  )
                })}
              </TableBody>
            </Table>
          </Card>
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted-foreground">
              {offset + 1}–{offset + items.length} of {total}
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={offset === 0 || query.isFetching}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={offset + PAGE_SIZE >= total || query.isFetching}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
