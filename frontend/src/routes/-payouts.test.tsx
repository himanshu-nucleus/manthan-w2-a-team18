import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { resetPayoutsMock } from '@/mocks/handlers/payouts'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

describe('payouts', () => {
  beforeEach(() => {
    resetPayoutsMock()
    setToken('mock-token-4')
  })
  afterEach(() => vi.restoreAllMocks())

  it('previews eligible claims with count and total', async () => {
    const user = userEvent.setup()
    renderRoute('/payouts')
    await user.click(await screen.findByRole('button', { name: 'Preview' }))
    const section = await screen.findByRole('region', { name: 'Eligible claims' })
    expect(await within(section).findByText('CLM-000201')).toBeInTheDocument()
    expect(within(section).getByText('CLM-000202')).toBeInTheDocument()
    expect(within(section).getByText(/2 eligible claims/)).toBeInTheDocument()
    expect(await screen.findByText('No payout batches yet.')).toBeInTheDocument()
  })

  it('creates a batch, toasts the reference, and lists it', async () => {
    const user = userEvent.setup()
    let body: unknown
    server.use(
      http.post('/api/v1/payouts/batches', async ({ request }) => {
        body = await request.clone().json()
        return undefined
      }),
    )
    renderRoute('/payouts')
    await user.click(await screen.findByRole('button', { name: 'Preview' }))
    await user.click(await screen.findByRole('button', { name: /Create batch & mark paid/ }))
    await user.click(await screen.findByRole('button', { name: 'Create batch' }))
    expect(body).toEqual({ range: 'TODAY' })
    expect(await screen.findByText(/Batch PB-\d{8}-001 created/)).toBeInTheDocument()
    const batches = await screen.findByRole('region', { name: 'Payout batches' })
    expect(await within(batches).findByText(/PB-\d{8}-001/)).toBeInTheDocument()
  })

  it('downloads the batch CSV via the export endpoint', async () => {
    const user = userEvent.setup()
    const exported = vi.fn<(id: unknown) => void>()
    server.use(
      http.get('/api/v1/payouts/batches/:id/export', ({ params }) => {
        exported(params.id)
        return new HttpResponse('csv', { headers: { 'Content-Type': 'text/csv' } })
      }),
    )
    URL.createObjectURL = vi.fn<() => string>(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn<() => void>()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    renderRoute('/payouts')
    await user.click(await screen.findByRole('button', { name: 'Preview' }))
    await user.click(await screen.findByRole('button', { name: /Create batch & mark paid/ }))
    await user.click(await screen.findByRole('button', { name: 'Create batch' }))
    await user.click(await screen.findByRole('button', { name: /Download CSV/ }))

    await vi.waitFor(() => expect(exported).toHaveBeenCalledWith('1'))
    await vi.waitFor(() => expect(click).toHaveBeenCalled())
  })
})
