const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/** `₹1,00,000` — Indian grouping, no paise (DESIGN.md §9). Amounts arrive as decimal strings. */
export function formatInr(amount: string | number | null | undefined) {
  if (amount === null || amount === undefined || amount === '') return '—'
  const value = typeof amount === 'number' ? amount : Number(amount)
  return Number.isFinite(value) ? inr.format(value) : '—'
}

const dayMonth = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' })
const dayMonthYear = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})
const time = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })

function toDate(value: string | Date) {
  // Plain `YYYY-MM-DD` dates are calendar days, not instants: parse them as local midnight.
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value)
}

/** `14 Nov`, or `14 Nov 2025` when not the current year. */
export function formatDate(value: string | Date | null | undefined) {
  if (!value) return '—'
  const date = toDate(value)
  return date.getFullYear() === new Date().getFullYear()
    ? dayMonth.format(date)
    : dayMonthYear.format(date)
}

/** `14 Nov, 16:20`. */
export function formatDateTime(value: string | Date | null | undefined) {
  if (!value) return '—'
  const date = toDate(value)
  return `${formatDate(date)}, ${time.format(date)}`
}

/** Relative age for tables: `5 m`, `5 h`, `2 d`. */
export function formatAge(value: string | Date | null | undefined, now = new Date()) {
  if (!value) return '—'
  const minutes = Math.max(0, Math.floor((now.getTime() - toDate(value).getTime()) / 60_000))
  if (minutes < 60) return `${minutes} m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h`
  return `${Math.floor(hours / 24)} d`
}

/** `EXP-2026-0007` style claim reference built from the numeric id and creation year. */
export function claimRef(id: number, createdAt?: string | null) {
  const year = createdAt ? new Date(createdAt).getFullYear() : new Date().getFullYear()
  return `EXP-${year}-${String(id).padStart(4, '0')}`
}
