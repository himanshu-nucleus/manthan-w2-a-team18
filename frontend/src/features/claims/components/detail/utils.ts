import type { Tone } from '@/components/status-chip'
import type { ApprovalStep } from '@/features/claims/api'

export const ROLE_LABEL: Record<string, string> = {
  employee: 'Employee',
  line_manager: 'Line manager',
  finance_auditor: 'Finance auditor',
  finance_head: 'Finance head',
}

export const STEP_STATUS: Record<string, { label: string; tone: Tone }> = {
  PENDING: { label: 'Pending', tone: 'info' },
  WAITING: { label: 'Waiting', tone: 'neutral' },
  APPROVED: { label: 'Approved', tone: 'success' },
  REJECTED: { label: 'Rejected', tone: 'danger' },
  SENT_BACK: { label: 'Sent back', tone: 'warning' },
}

export function personLabel(id: number | null | undefined, currentUserId: number, prefix = 'User') {
  if (id === null || id === undefined) return '—'
  return id === currentUserId ? 'You' : `${prefix} #${id}`
}

export function humanize(value: string) {
  const text = value.replace(/[._]/g, ' ').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Steps of the latest round, in chain order. */
export function currentRoundSteps(steps: ApprovalStep[]) {
  if (steps.length === 0) return []
  const round = Math.max(...steps.map((s) => s.round))
  return steps.filter((s) => s.round === round).sort((a, b) => a.step_order - b.step_order)
}
