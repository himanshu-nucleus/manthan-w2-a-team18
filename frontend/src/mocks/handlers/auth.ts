import { delay, http, HttpResponse } from 'msw'
import type { LoginRequest } from '@/features/auth/api'
import { MOCK_PASSWORD, mockUsers } from '../data'

const TOKEN_PREFIX = 'mock-token-'

function unauthorized(code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status: 401 })
}

export const authHandlers = [
  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as LoginRequest
    await delay()
    const user = mockUsers.find((u) => u.username === body.username.toLowerCase())
    if (!user?.is_active || body.password !== MOCK_PASSWORD) {
      return unauthorized('invalid_credentials', 'The username or password is incorrect.')
    }
    return HttpResponse.json({
      access_token: `${TOKEN_PREFIX}${user.id}`,
      token_type: 'bearer',
      expires_in: 28800,
      user,
    })
  }),

  http.get('/api/v1/auth/me', ({ request }) => {
    const token = request.headers.get('Authorization')?.replace(/^Bearer /, '') ?? ''
    const user = mockUsers.find((u) => `${TOKEN_PREFIX}${u.id}` === token)
    return user ? HttpResponse.json(user) : unauthorized('not_authenticated', 'Not signed in.')
  }),
]
