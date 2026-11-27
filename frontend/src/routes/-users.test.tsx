import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { createUser, users } from '@/mocks/data'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

describe('users route', () => {
  it('lists users from the mocked API', async () => {
    renderRoute('/users')
    expect(await screen.findByRole('heading', { name: 'Users' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(users.length)
    expect(screen.getByText(users[0].name)).toBeInTheDocument()
  })

  it('uses per-test handler overrides', async () => {
    server.use(
      http.get('/api/users', () => HttpResponse.json([createUser({ name: 'Ada Lovelace' })])),
    )
    renderRoute('/users')
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()
  })

  it('shows an error when the API fails', async () => {
    server.use(http.get('/api/users', () => new HttpResponse(null, { status: 500 })))
    renderRoute('/users')
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch users: 500')
  })
})
