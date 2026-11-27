import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoute } from '@/test/render'

describe('home route', () => {
  it('renders the app name and increments the counter', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    expect(await screen.findByRole('heading', { name: 'manthan-w2-a-team18' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /count is 0/i }))
    expect(screen.getByRole('button', { name: /count is 1/i })).toBeInTheDocument()
  })
})
