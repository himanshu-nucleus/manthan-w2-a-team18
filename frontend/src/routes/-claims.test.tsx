import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { resetClaimsStore } from '@/mocks/handlers/claims'
import { renderRoute } from '@/test/render'

// jsdom has no matchMedia; the app shell's responsive sidebar needs it.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
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
}

beforeEach(() => {
  resetClaimsStore()
  setToken('mock-token-1')
})

describe('my claims (E2)', () => {
  it('lists the employee claims with status chips and a new-claim action', async () => {
    renderRoute('/claims')
    expect((await screen.findAllByText('Bangalore offsite')).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'My claims' })).toBeInTheDocument()
    const row = screen.getAllByText('Bangalore offsite')[0].closest('tr')!
    expect(within(row).getByText('Pending approval')).toBeInTheDocument()
    expect(within(row).getByText('₹9,000')).toBeInTheDocument()
    const newLinks = screen.getAllByText('New claim').map((el) => el.closest('a'))
    expect(newLinks.some((a) => a?.getAttribute('href') === '/claims/new')).toBe(true)
  })

  it('filters by status via the search param', async () => {
    renderRoute('/claims?status=DRAFT')
    expect((await screen.findAllByText('Client visit — Pune')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Bangalore offsite')).not.toBeInTheDocument()
  })
})

describe('claim form', () => {
  it('requires city and nights for hotel lines on submit', async () => {
    const user = userEvent.setup()
    renderRoute('/claims/new')
    await user.type(await screen.findByLabelText('Claim title'), 'Trip')
    await user.selectOptions(screen.getByLabelText('Category'), 'hotel')
    await user.type(screen.getByLabelText('Amount (₹)'), '400')
    await user.type(screen.getByLabelText('Vendor'), 'Hotel X')
    await user.click(screen.getByRole('button', { name: 'Submit claim' }))
    expect(await screen.findByText('City is required for hotel stays')).toBeInTheDocument()
    expect(screen.getByText('Nights are required for hotel stays')).toBeInTheDocument()
    expect(screen.getByText('Enter the date')).toBeInTheDocument()
  })

  it('requires a receipt above 500 INR before submitting', async () => {
    const user = userEvent.setup()
    renderRoute('/claims/new')
    await user.type(await screen.findByLabelText('Claim title'), 'Trip')
    await user.selectOptions(screen.getByLabelText('Category'), 'meal')
    await user.type(screen.getByLabelText('Amount (₹)'), '900')
    await user.click(screen.getByRole('button', { name: 'Submit claim' }))
    expect(
      await screen.findAllByText('Receipt number and receipt file are required above ₹500'),
    ).toHaveLength(2)
  })

  it('saves a draft then submits and lands on the claim detail page', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/claims/new')
    await user.type(await screen.findByLabelText('Claim title'), 'Lunch')
    await user.selectOptions(screen.getByLabelText('Category'), 'meal')
    await user.type(screen.getByLabelText('Amount (₹)'), '300')
    await user.type(screen.getByLabelText('Expense date'), '2026-11-20')
    await user.type(screen.getByLabelText('Vendor'), 'Cafe')
    expect(screen.getByTestId('claim-total')).toHaveTextContent('₹300')

    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/claims/100/edit'))
    expect(await screen.findByDisplayValue('Lunch')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Submit claim' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/claims/100'))
  })

  it('refuses to edit a claim that is no longer editable', async () => {
    renderRoute('/claims/2/edit')
    expect(await screen.findByText("This claim can't be edited")).toBeInTheDocument()
    expect(screen.getByText('View claim').closest('a')).toHaveAttribute('href', '/claims/2')
  })
})
