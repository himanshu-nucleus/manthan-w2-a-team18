import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { todayIso } from '@/features/approvals/components/dates'
import { setToken } from '@/features/auth/token-storage'
import { resetApprovalsMock } from '@/mocks/handlers/approvals'
import { renderRoute } from '@/test/render'

function shiftDay(days: number) {
  const d = new Date(`${todayIso()}T00:00:00`)
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// jsdom lacks matchMedia, which sonner's <Toaster> (root layout) reads.
beforeAll(() => {
  window.matchMedia ??= (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
})

describe('out of office', () => {
  beforeEach(() => resetApprovalsMock())

  it('validates the dates', async () => {
    setToken('mock-token-2')
    const user = userEvent.setup()
    renderRoute('/delegations')
    const from = await screen.findByLabelText('From')
    await user.type(screen.getByLabelText('Delegate user ID'), '4')
    await user.clear(from)
    await user.type(from, shiftDay(-1))
    await user.type(screen.getByLabelText('To'), shiftDay(-3))
    await user.click(screen.getByRole('button', { name: 'Delegate approvals' }))
    expect(await screen.findByText('Start date cannot be in the past')).toBeInTheDocument()
    expect(screen.getByText('End date must be on or after the start date')).toBeInTheDocument()
  })

  it('creates a delegation and lists it', async () => {
    setToken('mock-token-2')
    const user = userEvent.setup()
    renderRoute('/delegations')
    await user.type(await screen.findByLabelText('Delegate user ID'), '3')
    await user.type(screen.getByLabelText('To'), shiftDay(2))
    await user.type(screen.getByLabelText('Reason (optional)'), 'Conference')
    await user.click(screen.getByRole('button', { name: 'Delegate approvals' }))
    expect(await screen.findByText(/Approvals delegated to User #3/)).toBeInTheDocument()
    const row = (await screen.findByText('Conference')).closest('tr')!
    expect(within(row).getByText('To User #3')).toBeInTheDocument()
    expect(within(row).getByText('Active now')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    // A received delegation is listed but cannot be cancelled.
    const received = screen.getByText('From User #5').closest('tr')!
    expect(within(received).queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
  })

  it('tells employees only approvers can delegate', async () => {
    setToken('mock-token-1')
    renderRoute('/delegations')
    expect(await screen.findByText(/Only approvers/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Delegate user ID')).not.toBeInTheDocument()
  })
})
