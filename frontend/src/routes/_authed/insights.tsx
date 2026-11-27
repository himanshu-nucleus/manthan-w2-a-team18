import { useQueries, useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import {
  BankIcon,
  ClockIcon,
  ReceiptIcon,
  WalletIcon,
  WarningIcon,
  type Icon,
} from '@phosphor-icons/react'
import { useMemo, type ReactNode } from 'react'
import { PageHeader } from '@/components/app-shell'
import { CLAIM_STATUS, POLICY_OUTCOME, StatusChip } from '@/components/status-chip'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { CATEGORY_LABEL, claimQuery, type ExpenseCategory } from '@/features/claims/api'
import {
  aggregateCategories,
  aggregateClaims,
  formatDuration,
  latestSubmitted,
  VIOLATION_OUTCOMES,
} from '@/features/insights/aggregate'
import { allClaimsQuery } from '@/features/insights/api'
import { formatInr } from '@/lib/format'

const CATEGORY_SAMPLE = 50

export const Route = createFileRoute('/_authed/insights')({
  component: InsightsPage,
})

function KpiCard({
  label,
  value,
  sub,
  icon: IconCmp,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon: Icon
}) {
  return (
    <div className="flex flex-col gap-2 rounded-card border bg-card p-[18px] shadow-xs">
      <div className="flex items-center gap-2">
        <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-primary">
          <IconCmp size={18} />
        </span>
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <div className="tabular text-[30px] leading-tight font-medium">{value}</div>
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  )
}

function Section({
  title,
  caption,
  children,
}: {
  title: string
  caption?: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="gap-3 rounded-card p-5">
      <div>
        <h2 className="text-base font-medium">{title}</h2>
        {caption ? <p className="text-xs text-muted-foreground">{caption}</p> : null}
      </div>
      {children}
    </Card>
  )
}

function HBars({ rows }: { rows: { label: ReactNode; value: number; display: ReactNode }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  if (!rows.length) return <p className="text-sm text-muted-foreground">No data yet.</p>
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((r, i) => (
        <li key={i} className="flex flex-col gap-1">
          <div className="flex justify-between gap-2 text-sm">
            <span>{r.label}</span>
            <span className="tabular font-medium">{r.display}</span>
          </div>
          <div className="h-2 rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-primary"
              style={{ width: `${(r.value / max) * 100}%`, opacity: 0.35 + 0.65 * (r.value / max) }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

function MonthChart({ data }: { data: { label: string; amount: number; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.amount))
  return (
    <div className="flex h-48 items-end gap-3" role="img" aria-label="Monthly spend bar chart">
      {data.map((d, i) => {
        const last = i === data.length - 1
        return (
          <div
            key={d.label + i}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1"
          >
            <span className="tabular text-[11px] text-muted-foreground">
              {d.amount ? formatInr(d.amount) : ''}
            </span>
            <div
              title={`${d.label}: ${formatInr(d.amount)} · ${d.count} claims`}
              className="w-full max-w-12 rounded-t-md bg-primary"
              style={{
                height: `${Math.max(2, (d.amount / max) * 100)}%`,
                opacity: last ? 1 : 0.25 + 0.6 * (d.amount / max),
              }}
            />
            <span className="text-xs text-muted-foreground">{d.label}</span>
          </div>
        )
      })}
    </div>
  )
}

function InsightsPage() {
  const { user } = Route.useRouteContext()
  const claimsQ = useQuery(allClaimsQuery())
  const claims = useMemo(() => claimsQ.data?.items ?? [], [claimsQ.data])
  const summary = useMemo(() => aggregateClaims(claims), [claims])

  const sample = useMemo(() => latestSubmitted(claims, CATEGORY_SAMPLE), [claims])
  const details = useQueries({
    queries: sample.map((c) => ({ ...claimQuery(c.id), staleTime: 60_000 })),
  })
  const detailsLoading = details.some((d) => d.isPending)
  // At most 50 claims' lines: cheap enough to recompute each render.
  const categories = aggregateCategories(details.flatMap((d) => (d.data ? [d.data] : [])))

  const pct = summary.submittedClaims
    ? `${((summary.violations / summary.submittedClaims) * 100).toFixed(1)}% of submitted claims`
    : 'No submitted claims'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={
          <span className="text-sm font-normal text-muted-foreground">Hi {user.full_name}</span>
        }
      />
      <div className="-mt-6">
        <h2 className="text-gradient-brand text-display font-medium">
          {claimsQ.isPending ? (
            <Skeleton className="h-10 w-96" />
          ) : (
            `${formatInr(summary.payoutAmount)} is ready for payout.`
          )}
        </h2>
        <p className="text-sm text-muted-foreground">
          Company-wide · {claimsQ.data?.total ?? '…'} claims
          {claimsQ.data && claimsQ.data.items.length < claimsQ.data.total
            ? ` (showing latest ${claimsQ.data.items.length})`
            : ''}
        </p>
      </div>

      {claimsQ.isError ? (
        <Card className="rounded-card p-5 text-sm text-destructive">
          Could not load claims: {String(claimsQ.error.message)}
        </Card>
      ) : null}

      <Section title="Finance overview">
        {claimsQ.isPending ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-28 rounded-card" />
            ))}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard
              label="Claims"
              icon={ReceiptIcon}
              value={summary.totalClaims.toLocaleString('en-IN')}
              sub={`${summary.submittedClaims} submitted`}
            />
            <KpiCard
              label="Total spend"
              icon={WalletIcon}
              value={formatInr(summary.totalSpend)}
              sub="Approved + paid"
            />
            <KpiCard
              label="Policy violations"
              icon={WarningIcon}
              value={summary.violations}
              sub={pct}
            />
            <KpiCard
              label="Avg approval time"
              icon={ClockIcon}
              value={formatDuration(summary.avgApprovalHours)}
              sub={`Across ${summary.approvedWithTiming} approved claims`}
            />
            <KpiCard
              label="Ready for payout"
              icon={BankIcon}
              value={formatInr(summary.payoutAmount)}
              sub={`${summary.payoutCount} approved, not yet paid`}
            />
          </div>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Monthly spend" caption="Claimed amount by submission month, last 6 months">
          {claimsQ.isPending ? (
            <Skeleton className="h-48" />
          ) : (
            <MonthChart data={summary.byMonth} />
          )}
        </Section>
        <Section title="Policy violations" caption="Claims by policy outcome">
          <HBars
            rows={VIOLATION_OUTCOMES.map((o) => ({
              label: <StatusChip {...POLICY_OUTCOME[o]} />,
              value: summary.violationsByOutcome[o] ?? 0,
              display: summary.violationsByOutcome[o] ?? 0,
            }))}
          />
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section
          title="Spend by category"
          caption={`Based on the latest ${sample.length} submitted claims`}
        >
          {detailsLoading && !categories.length ? (
            <Skeleton className="h-40" />
          ) : (
            <HBars
              rows={categories.map((c) => ({
                label: CATEGORY_LABEL[c.category as ExpenseCategory] ?? c.category,
                value: c.amount,
                display: formatInr(c.amount),
              }))}
            />
          )}
        </Section>
        <Section title="Status breakdown" caption="All claims by current status">
          <HBars
            rows={summary.byStatus.map((s) => ({
              label: (
                <StatusChip
                  {...(CLAIM_STATUS[s.status] ?? { label: s.status, tone: 'neutral' as const })}
                />
              ),
              value: s.count,
              display: `${s.count} · ${formatInr(s.amount)}`,
            }))}
          />
        </Section>
        <Section title="Spend by department">
          <p className="text-sm text-muted-foreground">
            Department breakdown needs a department field in the users API.
          </p>
        </Section>
      </div>
    </div>
  )
}
