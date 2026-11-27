import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { auditLogsHandlers } from '@/mocks/handlers/audit-logs'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

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

describe('audit trail', () => {
  beforeEach(() => {
    // Make sure the audit handlers are active even if index.ts wiring changes.
    server.use(...auditLogsHandlers)
    setToken('mock-token-4')
  })

  it('renders audit rows for the finance head', async () => {
    renderRoute('/audit-trail')
    expect(await screen.findByText('Looks fine')).toBeInTheDocument()
    expect(await bodyRows()).toHaveLength(4)
    expect(screen.getByText('Step approved')).toBeInTheDocument()
    expect(screen.getByText('User #5')).toBeInTheDocument()
    expect(screen.getByText(/Append-only/)).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole('button', { name: 'Show details for entry 4' }))
    expect(await screen.findByText('"APPROVED"')).toBeInTheDocument()
    expect(screen.getByText(/req-4/)).toBeInTheDocument()
  })

  it('sends the filters as query params', async () => {
    const user = userEvent.setup()
    const seen: URLSearchParams[] = []
    server.use(
      http.get('/api/v1/audit-logs', ({ request }) => {
        seen.push(new URL(request.url).searchParams)
        return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 })
      }),
    )
    renderRoute('/audit-trail')
    expect(await screen.findByText('No audit entries match')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Entity type'), 'claim')
    await user.type(screen.getByLabelText('Action'), 'APPROVED')
    await user.type(screen.getByLabelText('Claim id'), '101')
    await user.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      const last = seen.at(-1)
      expect(last?.get('entityType')).toBe('claim')
      expect(last?.get('action')).toBe('APPROVED')
      expect(last?.get('claimId')).toBe('101')
      expect(last?.get('offset')).toBe('0')
    })
  })

  it('verifies the hash chain', async () => {
    const user = userEvent.setup()
    renderRoute('/audit-trail')
    await user.click(await screen.findByRole('button', { name: 'Verify integrity' }))
    expect(await screen.findByText('Chain intact (4 rows)')).toBeInTheDocument()

    server.use(
      http.get('/api/v1/audit-logs/verify', () =>
        HttpResponse.json({
          checked: 3,
          valid: false,
          unchained_rows: 0,
          first_broken_id: 3,
          problem: 'hash mismatch',
        }),
      ),
    )
    await user.click(screen.getByRole('button', { name: 'Verify integrity' }))
    expect(await screen.findByText('Broken at row #3')).toBeInTheDocument()
  })
})
