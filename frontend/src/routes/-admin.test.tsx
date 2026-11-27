import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

// jsdom lacks matchMedia, which the app shell (toaster / sidebar) reads.
beforeAll(() => {
  window.matchMedia ??= (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
})

const signInAs = (id: number) => setToken(`mock-token-${id}`)

function captureRequests(method: string, pathEnd: string) {
  const bodies: unknown[] = []
  server.events.on('request:start', async ({ request }) => {
    if (request.method === method && new URL(request.url).pathname.endsWith(pathEnd)) {
      bodies.push(await request.clone().json())
    }
  })
  return bodies
}

describe('policy rules (F3)', () => {
  it('lists seeded rules with params and outcome', async () => {
    signInAs(4)
    renderRoute('/admin/policy-rules')
    expect(await screen.findByText('Meals up to 1,500 INR per day')).toBeInTheDocument()
    expect(screen.getByText('HOTEL_NIGHTLY_LIMIT_T1')).toBeInTheDocument()
    expect(screen.getByText('Limit: 6000 · City tier: tier1')).toBeInTheDocument()
    expect(screen.getAllByText('Auto-rejected').length).toBeGreaterThan(0)
  })

  it('edits a rule and sends only the changed params', async () => {
    signInAs(4)
    const bodies = captureRequests('PUT', '/policy-rules/CAB_TRIP_LIMIT')
    const user = userEvent.setup()
    renderRoute('/admin/policy-rules')
    await user.click(
      await screen.findByRole('button', { name: 'Edit Local cab up to 2,000 INR per trip' }),
    )

    const limit = await screen.findByLabelText('Limit')
    await user.clear(limit)
    await user.type(limit, '2500')
    await user.click(screen.getByRole('button', { name: 'Save rule' }))

    await waitFor(() => expect(bodies).toEqual([{ params: { limit: '2500' } }]))
    expect(await screen.findByText('Limit: 2500')).toBeInTheDocument()
    server.events.removeAllListeners()
  })

  it('is read-only for non finance head users', async () => {
    signInAs(1)
    renderRoute('/admin/policy-rules')
    expect(await screen.findByText('Meals up to 1,500 INR per day')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Edit / })).not.toBeInTheDocument()
    expect(screen.queryByText('Show inactive')).not.toBeInTheDocument()
  })
})

describe('people (F4)', () => {
  it('validates the add-person form, then creates the user with username from email', async () => {
    signInAs(4)
    const bodies = captureRequests('POST', '/users')
    const user = userEvent.setup()
    renderRoute('/admin/people')
    expect(
      (await screen.findAllByText('admin@expenseflow.example', { selector: 'td' })).length,
    ).toBe(2)

    await user.click(screen.getByRole('button', { name: 'Add person' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Add person' }))
    expect(await within(dialog).findByText('Enter a full name')).toBeInTheDocument()
    expect(within(dialog).getByText('Password must be at least 8 characters')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)

    await user.type(within(dialog).getByLabelText('Full name'), 'Priya Shah')
    await user.type(within(dialog).getByLabelText('Work email'), 'Priya.Shah@expenseflow.example')
    expect(within(dialog).getByLabelText('Username')).toHaveValue('priya.shah@expenseflow.example')
    await user.type(within(dialog).getByLabelText('Temporary password'), 'secret123')
    await user.click(within(dialog).getByRole('button', { name: 'Add person' }))

    await waitFor(() =>
      expect(bodies).toEqual([
        {
          full_name: 'Priya Shah',
          email: 'Priya.Shah@expenseflow.example',
          username: 'priya.shah@expenseflow.example',
          role: 'employee',
          password: 'secret123',
          manager_id: null,
        },
      ]),
    )
    expect(await screen.findByText('Priya Shah', { selector: 'td' })).toBeInTheDocument()
    server.events.removeAllListeners()
  })

  it('blocks people management for non finance head users', async () => {
    signInAs(3)
    renderRoute('/admin/people')
    expect(await screen.findByText('Only the finance head can manage people')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add person' })).not.toBeInTheDocument()
  })
})
