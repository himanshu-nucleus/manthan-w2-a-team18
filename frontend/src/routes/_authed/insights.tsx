import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import {
  ArrowDownIcon,
  ArrowUpIcon,
  BankIcon,
  ClockIcon,
  ReceiptIcon,
  WalletIcon,
  WarningIcon,
  type Icon,
} from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'
import { PageHeader } from '@/components/app-shell'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { CATEGORY_LABEL, type ExpenseCategory } from '@/features/claims/api'
import { dashboardSummaryQuery, type DashboardSummary } from '@/features/insights/summary-api'
import { ApiError, errorMessage } from '@/lib/api'
import { formatDateTime, formatInr } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_authed/insights')({
  component: InsightsPage,
})

const monthFmt = new Intl.DateTimeFormat('en-IN', { month: 'short', year: 'numeric' })
const shortMonthFmt = new Intl.DateTimeFormat('en-IN', { month: 'short' })

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function parseMonth(key: string) {
  const [y, m] = key.split('-').map(Number)
  return new Date(y, (m || 1) - 1, 1)
}

function lastTwelveMonths() {
  const now = new Date()
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    return { value: monthKey(d), label: monthFmt.format(d) }
  })
}

function formatHours(h: number | null) {
  if (h === null) return '—'
  if (h < 1) return `${Math.round(h * 60)}m`
  if (h < 48) return `${h.toFixed(1)}h`
  return `${(h / 24).toFixed(1)}d`
}

function humanise(action: string) {
  return action.toLowerCase().replaceAll('_', ' ')
}

/** ↑/↓ % vs previous month; `upIsGood` decides the colour. */
function Delta({
  value,
  previous,
  upIsGood,
}: {
  value: number | null
  previous: number | null
  upIsGood: boolean
}) {
  if (value === null || previous === null || previous === 0) {
    return <span className="text-xs text-muted-foreground">No prior-month data</span>
  }
  const pct = ((value - previous) / previous) * 100
  if (Math.abs(pct) < 0.05) {
    return <span className="text-xs text-muted-foreground">Same as last month</span>
  }
  const up = pct > 0
  const good = up === upIsGood
  const Arrow = up ? ArrowUpIcon : ArrowDownIcon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-xs font-medium',
        good ? 'text-success-foreground' : 'text-destructive',
      )}
    >
      <Arrow size={12} weight="bold" aria-hidden />
      {Math.abs(pct).toFixed(1)}% vs last month
    </span>
  )
}

function KpiCard({
  label,
  value,
  sub,
  delta,
  icon: IconCmp,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  delta?: ReactNode
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
      {delta}
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  )
}

function Section({
  title,
  caption,
  children,
  className,
}: {
  title: string
  caption?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('gap-3 rounded-card p-5', className)}>
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
  if (!rows.length) return <p className="text-sm text-muted-foreground">No spend this month.</p>
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

function MonthChart({
  data,
  selected,
}: {
  data: DashboardSummary['monthly_spend']
  selected: string
}) {
  const rows = data.map((d) => ({ ...d, value: Number(d.amount) || 0 }))
  const max = Math.max(1, ...rows.map((d) => d.value))
  if (!rows.length) return <p className="text-sm text-muted-foreground">No data yet.</p>
  return (
    <div className="flex h-48 items-end gap-3" role="img" aria-label="Monthly spend bar chart">
      {rows.map((d) => {
        const current = d.month === selected
        const label = shortMonthFmt.format(parseMonth(d.month))
        return (
          <div key={d.month} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
            <span className="tabular text-[11px] text-muted-foreground">
              {d.value ? formatInr(d.value) : ''}
            </span>
            <div
              title={`${label}: ${formatInr(d.value)} · ${d.claims} claims`}
              className="w-full max-w-12 rounded-t-md bg-primary"
              style={{
                height: `${Math.max(2, (d.value / max) * 100)}%`,
                opacity: current ? 1 : 0.25 + 0.6 * (d.value / max),
              }}
            />
            <span
              className={cn(
                'text-xs text-muted-foreground',
                current && 'font-medium text-foreground',
              )}
            >
              {label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function InsightsPage() {
  const { user } = Route.useRouteContext()
  const [month, setMonth] = useState('')
  const months = lastTwelveMonths()
  const q = useQuery(dashboardSummaryQuery(month || undefined))
  const forbidden = q.error instanceof ApiError && q.error.status === 403

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={
          <span className="text-sm font-normal text-muted-foreground">Hi {user.full_name}</span>
        }
        actions={
          forbidden ? null : (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              Month
              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-sm text-foreground"
              >
                <option value="">This month</option>
                {months.slice(1).map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
          )
        }
      />

      {forbidden ? (
        <Card className="rounded-card p-5">
          <h2 className="text-base font-medium">The dashboard is for the finance team</h2>
          <p className="text-sm text-muted-foreground">
            Only finance auditors and the finance head can see company-wide spend. Your own claims
            are on the{' '}
            <Link to="/claims" className="text-primary underline">
              claims page
            </Link>
            .
          </p>
        </Card>
      ) : q.isError ? (
        <Card className="rounded-card p-5 text-sm text-destructive">
          Could not load the dashboard: {errorMessage(q.error)}
        </Card>
      ) : (
        <Dashboard data={q.data} />
      )}
    </div>
  )
}

function Dashboard({ data }: { data: DashboardSummary | undefined }) {
  if (!data) {
    return (
      <>
        <Skeleton className="-mt-6 h-10 w-96 max-w-full" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-32 rounded-card" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-card" />
          <Skeleton className="h-64 rounded-card" />
        </div>
      </>
    )
  }
  const { kpis, needs_action: na } = data
  const monthLabel = monthFmt.format(parseMonth(data.month))
  const v = kpis.policy_violations

  return (
    <>
      <div className="-mt-6">
        <h2 className="text-gradient-brand text-display font-medium">
          {formatInr(kpis.ready_for_payout.amount)} is ready for payout.
        </h2>
        <p className="text-sm text-muted-foreground">
          {monthLabel} · {data.active_employees} active employees
        </p>
      </div>

      <Section title="Finance overview" caption={`${monthLabel} compared with the previous month`}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label="Claims"
            icon={ReceiptIcon}
            value={kpis.claims.value.toLocaleString('en-IN')}
            delta={
              <Delta value={kpis.claims.value} previous={kpis.claims.previous} upIsGood={false} />
            }
            sub="Submitted this month"
          />
          <KpiCard
            label="Total spend"
            icon={WalletIcon}
            value={formatInr(kpis.total_spend.value)}
            delta={
              <Delta
                value={Number(kpis.total_spend.value)}
                previous={Number(kpis.total_spend.previous)}
                upIsGood={false}
              />
            }
          />
          <KpiCard
            label="Policy violations"
            icon={WarningIcon}
            value={v.lines}
            delta={<Delta value={v.lines} previous={v.previous_lines} upIsGood={false} />}
            sub={`${v.rate_percent.toFixed(1)}% of ${v.total_lines} lines`}
          />
          <KpiCard
            label="Avg approval time"
            icon={ClockIcon}
            value={formatHours(kpis.approval_time.average_hours)}
            delta={
              <Delta
                value={kpis.approval_time.average_hours}
                previous={kpis.approval_time.previous_average_hours}
                upIsGood={false}
              />
            }
            sub={`Across ${kpis.approval_time.approved_claims} approved claims`}
          />
          <KpiCard
            label="Ready for payout"
            icon={BankIcon}
            value={formatInr(kpis.ready_for_payout.amount)}
            sub={`${kpis.ready_for_payout.claims} approved, not yet paid`}
          />
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Needs your action">
          <div className="flex flex-col gap-4">
            <Link
              to="/approvals"
              className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted"
            >
              <span className="text-sm">My pending approvals</span>
              <span className="tabular text-xl font-medium">{na.my_pending_approvals}</span>
            </Link>
            <div className="flex flex-col gap-2">
              <p className="text-sm">
                <span className="tabular font-medium">{na.high_value_pending.count}</span>{' '}
                high-value claims pending (over {formatInr(na.high_value_pending.threshold)})
              </p>
              <ul className="flex flex-col gap-1">
                {na.high_value_pending.claims.map((c) => (
                  <li key={c.id} className="flex justify-between gap-2 text-sm">
                    <Link
                      to="/claims/$claimId"
                      params={{ claimId: String(c.id) }}
                      className="truncate text-primary hover:underline"
                    >
                      {c.title || `Claim #${c.id}`} · {c.employee_name}
                    </Link>
                    <span className="tabular font-medium">{formatInr(c.total_amount)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Section>
        <Section title="Monthly spend" caption="Claimed amount by month" className="lg:col-span-2">
          <MonthChart data={data.monthly_spend} selected={data.month} />
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Spend by category" caption={monthLabel}>
          <HBars
            rows={data.spend_by_category.map((c) => ({
              label: CATEGORY_LABEL[c.category as ExpenseCategory] ?? c.category,
              value: Number(c.amount) || 0,
              display: formatInr(c.amount),
            }))}
          />
        </Section>
        <Section title="Spend by department" caption={monthLabel}>
          <HBars
            rows={data.spend_by_department.map((d) => ({
              label: d.department,
              value: Number(d.amount) || 0,
              display: formatInr(d.amount),
            }))}
          />
        </Section>
        <Section title="Recent finance events">
          {data.recent_events.length ? (
            <ul className="flex flex-col gap-2">
              {data.recent_events.map((e) => (
                <li key={e.id} className="flex flex-col text-sm">
                  <span>
                    <span className="font-medium">{e.actor_name}</span> {humanise(e.action)}{' '}
                    {e.entity_type === 'claim' ? (
                      <Link
                        to="/claims/$claimId"
                        params={{ claimId: String(e.entity_id) }}
                        className="text-primary hover:underline"
                      >
                        claim #{e.entity_id}
                      </Link>
                    ) : (
                      `${e.entity_type.replaceAll('_', ' ')} #${e.entity_id}`
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(e.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No recent events.</p>
          )}
        </Section>
      </div>
    </>
  )
}
