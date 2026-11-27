import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { renderRoute } from '@/test/render'

describe('insights dashboard', () => {
  it('shows KPIs and spend by department for the finance head', async () => {
    setToken('mock-token-4')
    renderRoute('/insights')
    expect(await screen.findByText('Policy violations')).toBeInTheDocument()
    expect(screen.getByText('Avg approval time')).toBeInTheDocument()
    expect(screen.getByText('18.5h')).toBeInTheDocument()
    expect(screen.getByText('Spend by department')).toBeInTheDocument()
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getByText('Airfare')).toBeInTheDocument()
  })

  it('tells an employee the dashboard is finance-only', async () => {
    setToken('mock-token-1')
    renderRoute('/insights')
    expect(await screen.findByText('The dashboard is for the finance team')).toBeInTheDocument()
  })
})
