import {
  BankIcon,
  CalendarXIcon,
  ChartBarIcon,
  ListChecksIcon,
  PlusIcon,
  ReceiptIcon,
  ScalesIcon,
  ShieldCheckIcon,
  SignOutIcon,
  UsersThreeIcon,
  type Icon,
} from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import type { Role, User } from '@/features/auth/api'
import { signOut } from '@/features/auth/session'

interface NavItem {
  to:
    | '/claims'
    | '/claims/new'
    | '/approvals'
    | '/delegations'
    | '/admin/policy-rules'
    | '/admin/people'
    | '/payouts'
    | '/insights'
  label: string
  icon: Icon
}

const MY_CLAIMS: NavItem = { to: '/claims', label: 'My claims', icon: ReceiptIcon }
const NEW_CLAIM: NavItem = { to: '/claims/new', label: 'New claim', icon: PlusIcon }
const OUT_OF_OFFICE: NavItem = { to: '/delegations', label: 'Out of office', icon: CalendarXIcon }

/** Sidebar per role (DESIGN.md §7.2), limited to screens the API supports today. */
export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  employee: [MY_CLAIMS, NEW_CLAIM],
  line_manager: [
    { to: '/approvals', label: 'Approvals', icon: ListChecksIcon },
    MY_CLAIMS,
    NEW_CLAIM,
    OUT_OF_OFFICE,
  ],
  finance_auditor: [
    { to: '/approvals', label: 'Audit queue', icon: ShieldCheckIcon },
    { to: '/payouts', label: 'Payout batches', icon: BankIcon },
    MY_CLAIMS,
    NEW_CLAIM,
    OUT_OF_OFFICE,
  ],
  finance_head: [
    { to: '/insights', label: 'Dashboard', icon: ChartBarIcon },
    { to: '/approvals', label: 'Approvals', icon: ListChecksIcon },
    { to: '/payouts', label: 'Payout batches', icon: BankIcon },
    { to: '/claims', label: 'All claims', icon: ReceiptIcon },
    { to: '/admin/policy-rules', label: 'Policy rules', icon: ScalesIcon },
    { to: '/admin/people', label: 'People', icon: UsersThreeIcon },
    OUT_OF_OFFICE,
  ],
}

export const ROLE_LABEL: Record<Role, string> = {
  employee: 'Employee',
  line_manager: 'Line manager',
  finance_auditor: 'Finance auditor',
  finance_head: 'Finance head',
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

export function AppShell({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const handleSignOut = () => {
    signOut(queryClient)
    void navigate({ to: '/login', replace: true })
  }

  return (
    <div className="flex min-h-svh flex-col bg-background md:flex-row">
      <aside className="flex shrink-0 flex-col gap-4 border-b bg-sidebar px-4 pt-5 pb-4 md:sticky md:top-0 md:h-svh md:w-[260px] md:border-r md:border-b-0 md:pt-6">
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex size-8 items-center justify-center rounded-lg bg-(image:--gradient-brand) text-white">
            <ReceiptIcon size={18} />
          </span>
          <span className="text-lg font-semibold">ExpenseFlow</span>
          <span className="ml-auto rounded-full bg-sidebar-accent px-2.5 py-1 text-xs font-medium text-accent-foreground md:hidden">
            {ROLE_LABEL[user.role]}
          </span>
        </div>

        <nav aria-label="Main" className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV_BY_ROLE[user.role].map(({ to, label, icon: NavIcon }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: to === '/claims' }}
              className="flex h-10 shrink-0 items-center gap-2.5 rounded-[12px] px-3 text-sm font-medium whitespace-nowrap text-sidebar-foreground hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              activeProps={{ className: 'bg-night text-white hover:bg-transparent' }}
            >
              <NavIcon size={18} aria-hidden />
              {label}
            </Link>
          ))}
        </nav>

        <div className="mt-auto hidden items-center gap-2.5 rounded-full bg-muted p-1.5 pr-2 md:flex">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
            {initials(user.full_name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-medium">{user.full_name}</span>
            <span className="truncate text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</span>
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto rounded-full"
            aria-label="Sign out"
            onClick={handleSignOut}
          >
            <SignOutIcon />
          </Button>
        </div>
        <Button variant="outline" className="md:hidden" onClick={handleSignOut}>
          <SignOutIcon data-icon="inline-start" />
          Sign out
        </Button>
      </aside>

      <main className="min-w-0 flex-1 px-4 pt-6 pb-10 md:px-8">{children}</main>
    </div>
  )
}

/** Breadcrumb + H3 title + right-aligned actions (DESIGN.md §6). */
export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-h3 font-medium">{title}</h1>
          {children}
        </div>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
