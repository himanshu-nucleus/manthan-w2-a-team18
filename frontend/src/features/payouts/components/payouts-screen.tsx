import {
  CaretDownIcon,
  CaretRightIcon,
  DownloadSimpleIcon,
  MoneyIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Fragment, useState } from 'react'
import { toast } from 'sonner'
import { StatusChip } from '@/components/status-chip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { claimKeys } from '@/features/claims/api'
import {
  batchesQuery,
  batchQuery,
  createBatch,
  downloadBatchCsv,
  eligibleQuery,
  payoutKeys,
  type BatchSummary,
  type PayoutRange,
} from '@/features/payouts/api'
import { errorMessage } from '@/lib/api'
import { formatDate, formatDateTime, formatInr } from '@/lib/format'

function todayLocal() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function ErrorAlert({
  title,
  error,
  retry,
}: {
  title: string
  error: unknown
  retry?: () => void
}) {
  return (
    <Alert variant="destructive">
      <WarningCircleIcon />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-2">
        {errorMessage(error)}
        {retry && (
          <Button size="sm" variant="outline" onClick={retry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

function LoadingCard({ label }: { label: string }) {
  return (
    <Card className="flex flex-col gap-2 p-4" aria-label={label}>
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </Card>
  )
}

export function PayoutsScreen() {
  const [mode, setMode] = useState<'TODAY' | 'CUSTOM'>('TODAY')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [range, setRange] = useState<PayoutRange | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const queryClient = useQueryClient()
  const today = todayLocal()

  const preview = useQuery({ ...eligibleQuery(range ?? { range: 'TODAY' }), enabled: !!range })

  const create = useMutation({
    mutationFn: createBatch,
    onSuccess: async (batch) => {
      toast.success(`Batch ${batch.batch_reference} created`, {
        description: `${batch.claim_count} claims · ${formatInr(batch.total_amount)} marked paid`,
      })
      setConfirmOpen(false)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: payoutKeys.all }),
        queryClient.invalidateQueries({ queryKey: claimKeys.all }),
      ])
    },
    onError: (err) => {
      setConfirmOpen(false)
      toast.error("Couldn't create the batch", { description: errorMessage(err) })
    },
  })

  const customInvalid = mode === 'CUSTOM' && (!fromDate || !toDate || fromDate > toDate)

  function runPreview() {
    setRange(mode === 'TODAY' ? { range: 'TODAY' } : { fromDate, toDate })
  }

  const data = preview.data

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Approval date</span>
            <div role="group" aria-label="Range" className="flex gap-1">
              {(['TODAY', 'CUSTOM'] as const).map((m) => (
                <Button
                  key={m}
                  type="button"
                  size="sm"
                  variant={mode === m ? 'default' : 'outline'}
                  aria-pressed={mode === m}
                  onClick={() => setMode(m)}
                >
                  {m === 'TODAY' ? 'Today' : 'Custom'}
                </Button>
              ))}
            </div>
          </div>
          {mode === 'CUSTOM' && (
            <div className="flex items-center gap-1">
              <Input
                aria-label="From date"
                type="date"
                max={today}
                className="h-8 w-36"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
              <span className="text-muted-foreground">–</span>
              <Input
                aria-label="To date"
                type="date"
                max={today}
                className="h-8 w-36"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </div>
          )}
          <Button size="sm" variant="outline" disabled={customInvalid} onClick={runPreview}>
            Preview
          </Button>
        </div>
      </Card>

      {range &&
        (preview.isPending ? (
          <LoadingCard label="Loading eligible claims" />
        ) : preview.isError ? (
          <ErrorAlert
            title="Couldn't load eligible claims"
            error={preview.error}
            retry={() => preview.refetch()}
          />
        ) : data ? (
          <section className="flex flex-col gap-3" aria-label="Eligible claims">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                {data.claim_count} eligible {data.claim_count === 1 ? 'claim' : 'claims'} ·{' '}
                <span className="tabular font-medium text-foreground">
                  {formatInr(data.total_amount)}
                </span>{' '}
                · approved {formatDate(data.from_date)}
                {data.from_date !== data.to_date && ` – ${formatDate(data.to_date)}`}
              </p>
              <Button
                size="sm"
                disabled={data.claim_count === 0 || create.isPending}
                onClick={() => setConfirmOpen(true)}
              >
                <MoneyIcon />
                Create batch & mark paid
              </Button>
            </div>
            {data.claims.length === 0 ? (
              <Card className="px-6 py-10 text-center text-sm text-muted-foreground">
                No approved claims waiting for payout in this range.
              </Card>
            ) : (
              <Card className="overflow-x-auto p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-4">Claim</TableHead>
                      <TableHead>Employee</TableHead>
                      <TableHead>Department</TableHead>
                      <TableHead>Approved</TableHead>
                      <TableHead className="pr-4 text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.claims.map((c) => (
                      <TableRow key={c.claim_id}>
                        <TableCell className="pl-4">
                          <Link
                            to="/claims/$claimId"
                            params={{ claimId: String(c.claim_id) }}
                            className="font-medium text-primary hover:underline"
                          >
                            {c.claim_code}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span>{c.beneficiary_name}</span>
                            <span className="text-xs text-muted-foreground">
                              Employee #{c.employee_id}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>{c.department ?? '—'}</TableCell>
                        <TableCell>{formatDateTime(c.approved_at)}</TableCell>
                        <TableCell className="tabular pr-4 text-right font-medium">
                          {formatInr(c.amount)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </section>
        ) : null)}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create payout batch?</DialogTitle>
            <DialogDescription>
              {data?.claim_count} claims totalling {formatInr(data?.total_amount)} will be added to
              one batch and marked paid. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!range || create.isPending}
              onClick={() => range && create.mutate(range)}
            >
              {create.isPending ? 'Creating…' : 'Create batch'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <BatchesList />
    </div>
  )
}

function BatchesList() {
  const query = useQuery(batchesQuery())
  const [openId, setOpenId] = useState<number | null>(null)
  const [downloading, setDownloading] = useState<number | null>(null)
  const queryClient = useQueryClient()

  async function download(batch: BatchSummary) {
    setDownloading(batch.id)
    try {
      await downloadBatchCsv(batch)
      await queryClient.invalidateQueries({ queryKey: payoutKeys.all })
    } catch (err) {
      toast.error("Couldn't download the CSV", { description: errorMessage(err) })
    } finally {
      setDownloading(null)
    }
  }

  return (
    <section className="flex flex-col gap-3" aria-label="Payout batches">
      <h2 className="text-lg font-semibold">Batches</h2>
      {query.isPending ? (
        <LoadingCard label="Loading batches" />
      ) : query.isError ? (
        <ErrorAlert
          title="Couldn't load batches"
          error={query.error}
          retry={() => query.refetch()}
        />
      ) : query.data.items.length === 0 ? (
        <Card className="px-6 py-10 text-center text-sm text-muted-foreground">
          No payout batches yet.
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8 pl-4">
                  <span className="sr-only">Expand</span>
                </TableHead>
                <TableHead>Reference</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Claims</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="pr-4">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.items.map((b) => {
                const open = openId === b.id
                return (
                  <Fragment key={b.id}>
                    <TableRow>
                      <TableCell className="pl-4">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-expanded={open}
                          aria-label={`${open ? 'Hide' : 'Show'} claims in ${b.batch_reference}`}
                          onClick={() => setOpenId(open ? null : b.id)}
                        >
                          {open ? <CaretDownIcon /> : <CaretRightIcon />}
                        </Button>
                      </TableCell>
                      <TableCell className="font-medium">{b.batch_reference}</TableCell>
                      <TableCell>{formatDateTime(b.created_at)}</TableCell>
                      <TableCell>{b.claim_count}</TableCell>
                      <TableCell className="tabular text-right font-medium">
                        {formatInr(b.total_amount)}
                      </TableCell>
                      <TableCell>
                        <StatusChip
                          tone={b.status === 'EXPORTED' ? 'success' : 'info'}
                          label={b.status === 'EXPORTED' ? 'Exported' : 'Created'}
                        />
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={downloading === b.id}
                          onClick={() => download(b)}
                        >
                          <DownloadSimpleIcon />
                          Download CSV
                        </Button>
                      </TableCell>
                    </TableRow>
                    {open && (
                      <TableRow>
                        <TableCell colSpan={7} className="bg-muted/40 p-0">
                          <BatchItems id={b.id} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </section>
  )
}

function BatchItems({ id }: { id: number }) {
  const query = useQuery(batchQuery(id))
  if (query.isPending) return <Skeleton className="m-4 h-9" aria-label="Loading batch" />
  if (query.isError) {
    return (
      <div className="p-4">
        <ErrorAlert title="Couldn't load the batch" error={query.error} />
      </div>
    )
  }
  return (
    <Table aria-label={`Claims in ${query.data.batch_reference}`}>
      <TableHeader>
        <TableRow>
          <TableHead className="pl-12">Transaction</TableHead>
          <TableHead>Claim</TableHead>
          <TableHead>Employee</TableHead>
          <TableHead className="pr-4 text-right">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {query.data.items.map((i) => (
          <TableRow key={i.transaction_reference}>
            <TableCell className="pl-12 text-muted-foreground">{i.transaction_reference}</TableCell>
            <TableCell>
              <Link
                to="/claims/$claimId"
                params={{ claimId: String(i.claim_id) }}
                className="text-primary hover:underline"
              >
                {i.claim_code}
              </Link>
            </TableCell>
            <TableCell>
              {i.beneficiary_name}{' '}
              <span className="text-xs text-muted-foreground">({i.employee_code})</span>
            </TableCell>
            <TableCell className="tabular pr-4 text-right">{formatInr(i.amount)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
