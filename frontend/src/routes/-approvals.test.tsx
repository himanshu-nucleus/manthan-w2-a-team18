import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { resetApprovalsMock } from '@/mocks/handlers/approvals'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

const year = new Date().getFullYear()
const ref = (id: number) => `EXP-${year}-${String(id).padStart(4, '0')}`

async function bodyRows() {
  const table = await screen.findByRole('table')
  return within(table).getAllByRole('row').slice(1)
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

describe('approvals queue', () => {
  beforeEach(() => {
    resetApprovalsMock()
    setToken('mock-token-2')
  })

  it('renders the pending items as rows', async () => {
    renderRoute('/approvals')
    expect(await screen.findByText(ref(101))).toBeInTheDocument()
    expect(await bodyRows()).toHaveLength(4)
    expect(screen.getByText('Client visit Pune')).toBeInTheDocument()
    expect(screen.getByText('on behalf of User #5')).toBeInTheDocument()
    expect(screen.getByText('4 waiting for your approval')).toBeInTheDocument()
  })

  it('narrows rows with the client-side filters', async () => {
    const user = userEvent.setup()
    renderRoute('/approvals')
    await screen.findByText(ref(101))

    await user.click(screen.getByRole('button', { name: 'Needs approval' }))
    expect(await bodyRows()).toHaveLength(2)

    await user.type(screen.getByLabelText('Minimum amount'), '20000')
    const rows = await bodyRows()
    expect(rows).toHaveLength(1)
    expect(within(rows[0]).getByText(ref(103))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reset filters' }))
    await user.type(screen.getByLabelText('Search'), 'lunch')
    expect(await bodyRows()).toHaveLength(1)
    expect(screen.getByText('Team lunch')).toBeInTheDocument()
  })

  it('bulk-approves each selected row and reports failures', async () => {
    const approved: { id: string; body: unknown }[] = []
    server.events.on('request:start', async ({ request }) => {
      const m = /\/claims\/(\d+)\/approve$/.exec(new URL(request.url).pathname)
      if (m) approved.push({ id: m[1], body: await request.clone().json() })
    })
    server.use(
      http.post('/api/v1/claims/102/approve', () =>
        HttpResponse.json(
          { error: { code: 'not_current_approver', message: 'Not your step.' } },
          { status: 403 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderRoute('/approvals')
    await screen.findByText(ref(101))

    await user.click(screen.getByRole('checkbox', { name: `Select ${ref(101)}` }))
    await user.click(screen.getByRole('checkbox', { name: `Select ${ref(102)}` }))
    const bar = screen.getByRole('region', { name: 'Bulk actions' })
    expect(within(bar).getByText(/2 claims selected/)).toBeInTheDocument()

    await user.click(within(bar).getByRole('button', { name: /Approve 2/ }))
    expect(await screen.findByText('Approved 1 of 2')).toBeInTheDocument()
    expect(screen.getByText(/Not your step/)).toBeInTheDocument()
    expect(approved.map((a) => a.id).sort()).toEqual(['101', '102'])
    expect(approved.find((a) => a.id === '101')?.body).toEqual({ step_id: 1010 })
    await waitFor(() => expect(screen.queryByText(ref(101))).not.toBeInTheDocument())
    server.events.removeAllListeners()
  })

  it('selects all filtered rows', async () => {
    const user = userEvent.setup()
    renderRoute('/approvals')
    await screen.findByText(ref(101))
    await user.click(screen.getByRole('button', { name: 'Within policy' }))
    await user.click(screen.getByRole('checkbox', { name: 'Select all' }))
    expect(screen.getByText(/2 claims selected/)).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    server.use(
      http.get('/api/v1/approvals/pending', () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    )
    renderRoute('/approvals')
    expect(await screen.findByText('Nothing waiting for you')).toBeInTheDocument()
  })
})
