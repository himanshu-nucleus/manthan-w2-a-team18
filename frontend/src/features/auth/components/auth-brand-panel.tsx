import {
  BankIcon,
  ReceiptIcon,
  ShieldCheckIcon,
  SparkleIcon,
  TreeStructureIcon,
  type Icon,
} from '@phosphor-icons/react'

interface Feature {
  icon: Icon
  title: string
  description: string
}

// Marketing copy from the L1 design. The ₹ figures are illustrative: real limits are seeded
// policy configuration, so never read business rules from here.
const FEATURES: Feature[] = [
  {
    icon: ShieldCheckIcon,
    title: 'Live policy engine',
    description: 'Auto-approve, route or auto-reject with a reason',
  },
  {
    icon: TreeStructureIcon,
    title: 'Multi-level approvals',
    description: 'Manager → auditor above ₹25,000 → finance head above ₹1,00,000',
  },
  {
    icon: BankIcon,
    title: 'One-click payout batch',
    description: 'Bank-ready CSV, then claims move to Paid',
  },
]

const STARS = [
  'top-[12%] left-[82%]',
  'top-[16%] left-[14%]',
  'top-[27%] left-[74%]',
  'top-[42%] left-[90%]',
  'top-[71%] left-[84%]',
]

/** Left half of the L1 login screen: product pitch on the night gradient. */
export function AuthBrandPanel() {
  return (
    <aside className="bg-night relative hidden w-[640px] shrink-0 flex-col overflow-hidden rounded-[32px] px-12 pt-10 pb-12 text-white lg:flex">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-40 size-[560px] rounded-full bg-blue-600/35 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -bottom-24 size-[360px] rounded-full bg-violet-500/45 blur-3xl"
      />
      {STARS.map((position) => (
        <span
          key={position}
          aria-hidden
          className={`absolute size-0.5 rounded-full bg-white/80 ${position}`}
        />
      ))}

      <div className="relative flex items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-lg bg-(image:--gradient-brand)">
          <ReceiptIcon size={20} />
        </span>
        <span className="text-lg font-semibold">ExpenseFlow</span>
      </div>

      <div className="relative mt-auto flex flex-col gap-6">
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1.5 text-sm">
          <SparkleIcon weight="fill" size={14} />
          Policy-driven expense claims
        </span>

        <h2 className="text-5xl/[56px] font-medium tracking-tight">
          Claims in minutes.
          <span className="block bg-(image:--gradient-brand-soft) bg-clip-text text-transparent">
            Approvals in hours.
          </span>
        </h2>

        <p className="text-base text-white/80">
          Every line is checked against policy as you type. Duplicates are caught before payout, and
          every action is written to an append-only audit trail.
        </p>

        <ul className="flex flex-col gap-3">
          {FEATURES.map(({ icon: FeatureIcon, title, description }) => (
            <li
              key={title}
              className="flex items-center gap-3.5 rounded-2xl border border-white/15 bg-white/5 p-3.5"
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-white/10">
                <FeatureIcon size={18} />
              </span>
              <span className="flex flex-col">
                <span className="text-sm font-semibold">{title}</span>
                <span className="text-xs text-white/70">{description}</span>
              </span>
            </li>
          ))}
        </ul>

        <p className="mt-4 text-xs text-white/60">© 2026 ExpenseFlow · NucleusTeq</p>
      </div>
    </aside>
  )
}
