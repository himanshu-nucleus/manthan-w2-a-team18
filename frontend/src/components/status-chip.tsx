import {
  CheckCircleIcon,
  ClockIcon,
  InfoIcon,
  SparkleIcon,
  WarningIcon,
  XCircleIcon,
  type Icon,
} from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand'

const TONE_CLASS: Record<Tone, string> = {
  success: 'bg-success text-success-foreground border-success-border',
  warning: 'bg-warning text-warning-foreground border-warning-border',
  danger: 'bg-danger text-danger-foreground border-danger-border',
  info: 'bg-info text-info-foreground border-info-border',
  neutral: 'bg-neutral text-neutral-foreground border-neutral-border',
  brand: 'bg-brand text-brand-foreground border-brand-border',
}

const TONE_ICON: Record<Tone, Icon> = {
  success: CheckCircleIcon,
  warning: WarningIcon,
  danger: XCircleIcon,
  info: InfoIcon,
  neutral: ClockIcon,
  brand: SparkleIcon,
}

interface StatusChipProps {
  tone: Tone
  label: string
  className?: string
}

/** Status pill from DESIGN.md §7.2: always icon + label, never colour alone. */
export function StatusChip({ tone, label, className }: StatusChipProps) {
  const ChipIcon = TONE_ICON[tone]
  return (
    <span
      className={cn(
        'inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border py-0.5 pr-2.5 pl-2 text-xs font-medium whitespace-nowrap',
        TONE_CLASS[tone],
        className,
      )}
    >
      <ChipIcon size={13} weight={tone === 'brand' ? 'fill' : 'regular'} aria-hidden />
      {label}
    </span>
  )
}

/** Claim status (ClaimStatus in docs/openapi.json) → label + tone. */
export const CLAIM_STATUS: Record<string, { label: string; tone: Tone }> = {
  DRAFT: { label: 'Draft', tone: 'neutral' },
  SUBMITTED: { label: 'Submitted', tone: 'info' },
  AUTO_APPROVED: { label: 'Auto-approved', tone: 'success' },
  AUTO_REJECTED: { label: 'Auto-rejected', tone: 'danger' },
  PENDING_APPROVAL: { label: 'Pending approval', tone: 'info' },
  APPROVED: { label: 'Approved', tone: 'success' },
  REJECTED: { label: 'Rejected', tone: 'danger' },
  CLARIFICATION_REQUESTED: { label: 'Sent back', tone: 'warning' },
}

export function ClaimStatusChip({ status, className }: { status: string; className?: string }) {
  const meta = CLAIM_STATUS[status] ?? { label: status, tone: 'neutral' as const }
  return <StatusChip tone={meta.tone} label={meta.label} className={className} />
}

/** Policy outcome (per line or per claim) → label + tone. */
export const POLICY_OUTCOME: Record<string, { label: string; tone: Tone }> = {
  AUTO_APPROVE: { label: 'Within policy', tone: 'success' },
  ROUTE_FOR_APPROVAL: { label: 'Needs approval', tone: 'warning' },
  AUTO_REJECT: { label: 'Auto-rejected', tone: 'danger' },
}

export function PolicyOutcomeChip({
  outcome,
  className,
}: {
  outcome: string | null
  className?: string
}) {
  if (!outcome) return null
  const meta = POLICY_OUTCOME[outcome] ?? { label: outcome, tone: 'neutral' as const }
  return <StatusChip tone={meta.tone} label={meta.label} className={className} />
}
