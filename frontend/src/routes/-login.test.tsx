import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { getToken, setToken } from '@/features/auth/token-storage'
import { MOCK_PASSWORD, mockUsers } from '@/mocks/data'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

const employee = mockUsers[0]

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Work email'), email)
  if (password) await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('login page', () => {
  it('shows required-field errors when submitted empty and does not call the API', async () => {
    let called = false
    server.use(http.post('/api/v1/auth/login', () => void (called = true)))
    renderRoute('/login')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Enter your work email')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('rejects an email that is not an email address', async () => {
    renderRoute('/login')
    await fillAndSubmit('not-an-email', 'secret')
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
  })

  it('sends the email as username, stores the token and lands on the dashboard', async () => {
    let sentBody: unknown
    server.events.on('request:start', async ({ request }) => {
      if (request.url.endsWith('/auth/login')) sentBody = await request.clone().json()
    })
    const { router } = renderRoute('/login')
    await fillAndSubmit(employee.email!, MOCK_PASSWORD)

    expect(await screen.findByText(`Hi ${employee.full_name}`)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/dashboard')
    expect(sentBody).toEqual({ username: employee.email, password: MOCK_PASSWORD })
    expect(getToken()).toBe(`mock-token-${employee.id}`)
    server.events.removeAllListeners()
  })

  it('shows an error, keeps the email and clears the password on wrong credentials', async () => {
    renderRoute('/login')
    await fillAndSubmit(employee.email!, 'wrong-password')

    expect(await screen.findByText('Email or password is incorrect.')).toBeInTheDocument()
    expect(screen.getByLabelText('Work email')).toHaveValue(employee.email)
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(getToken()).toBeNull()
  })

  it('shows a connection error when the server fails', async () => {
    server.use(http.post('/api/v1/auth/login', () => HttpResponse.error()))
    renderRoute('/login')
    await fillAndSubmit(employee.email!, MOCK_PASSWORD)
    expect(await screen.findByText(/couldn't sign you in/i)).toBeInTheDocument()
  })

  it('returns to the page in ?redirect= after signing in', async () => {
    const { router } = renderRoute('/dashboard')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/dashboard' })

    await fillAndSubmit(employee.email!, MOCK_PASSWORD)
    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
  })

  it('ignores an off-site ?redirect=', async () => {
    const { router } = renderRoute('/login?redirect=//evil.example')
    await fillAndSubmit(employee.email!, MOCK_PASSWORD)
    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
  })

  it('skips the login page when a valid session already exists', async () => {
    setToken(`mock-token-${employee.id}`)
    const { router } = renderRoute('/login')
    expect(await screen.findByText(`Hi ${employee.full_name}`)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/dashboard')
  })
})

describe('protected routes', () => {
  it('send a signed-out visitor to the login page', async () => {
    const { router } = renderRoute('/')
    expect(await screen.findByRole('heading', { name: 'Sign in to your account' })).toBeVisible()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('drop an expired token and send the user to the login page', async () => {
    setToken('mock-token-expired')
    const { router } = renderRoute('/dashboard')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(getToken()).toBeNull()
  })

  it('sign the user out', async () => {
    setToken(`mock-token-${employee.id}`)
    const { router } = renderRoute('/dashboard')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(getToken()).toBeNull()
  })
})
