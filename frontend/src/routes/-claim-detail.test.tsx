import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, describe, expect, it } from 'vitest'
import { setToken } from '@/features/auth/token-storage'
import { mockUsers } from '@/mocks/data'
import { server } from '@/mocks/node'
import { renderRoute } from '@/test/render'

const [employee, manager] = mockUsers

// sonner's <Toaster> (root layout) reads matchMedia, which jsdom lacks.
beforeAll(() => {
  if (!window.matchMedia) {
    window.matchMedia = (query: string) =>
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
  }
})
const NOW = '2026-11-20T10:00:00Z'

function claimFixture(status: string) {
  return {
    id: 7,
    employee_id: employee.id,
    title: 'Mumbai client visit',
    currency: 'INR',
    status,
    total_amount: '30000.00',
    submitted_at: status === 'DRAFT' ? null : NOW,
    policy_outcome: status === 'DRAFT' ? null : 'ROUTE_FOR_APPROVAL',
    submission_round: 1,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
    policy_evaluated_at: null,
    created_by: employee.id,
    updated_by: employee.id,
    lines: [
      {
        id: 1,
        position: 1,
        category: 'hotel',
        amount: '28000.00',
        expense_date: '2026-11-10',
        vendor: 'Taj Lands End',
        description: null,
        city: 'Mumbai',
        nights: 4,
        receipt_number: 'R-1',
        receipt_id: 11,
      },
      {
        id: 2,
        position: 2,
        category: 'cab',
        amount: '2000.00',
        expense_date: '2026-11-11',
        vendor: 'Uber',
        description: 'Airport drop',
        city: null,
        nights: null,
        receipt_number: null,
        receipt_id: null,
      },
    ],
    attachments: [
      {
        id: 11,
        claim_id: 7,
        original_name: 'hotel.png',
        content_type: 'image/png',
        size_bytes: 10,
        sha256: 'x',
        uploaded_by: employee.id,
        uploaded_at: NOW,
      },
    ],
  }
}

function mockClaim(status: string) {
  let rejectBody: unknown
  server.use(
    http.get('/api/v1/claims/7', () => HttpResponse.json(claimFixture(status))),
    http.get('/api/v1/claims/7/policy-results', () =>
      HttpResponse.json({
        claim_id: 7,
        round: 1,
        outcome: 'ROUTE_FOR_APPROVAL',
        evaluated_at: NOW,
        lines: [
          {
            line_position: 1,
            outcome: 'ROUTE_FOR_APPROVAL',
            rule_codes: ['HOTEL_NIGHTLY_LIMIT_T1'],
            reasons: [
              'Hotel 7,000.00 INR per night in Mumbai exceeds tier-1 limit of 6,000.00 INR',
            ],
            rule_snapshot: {},
            evaluated_at: NOW,
          },
        ],
        claim_level: [
          {
            line_position: null,
            outcome: 'ROUTE_FOR_APPROVAL',
            rule_codes: ['AUTO_APPROVE_LIMIT'],
            reasons: ['Total above auto-approve limit'],
            rule_snapshot: {},
            evaluated_at: NOW,
          },
        ],
      }),
    ),
    http.get('/api/v1/claims/7/approval-steps', () =>
      HttpResponse.json(
        status === 'PENDING_APPROVAL'
          ? [
              {
                id: 41,
                claim_id: 7,
                round: 1,
                step_order: 1,
                approver_role: 'line_manager',
                assigned_approver_id: manager.id,
                status: 'PENDING',
                acted_by_id: null,
                on_behalf_of_id: null,
                acted_at: null,
                comment: null,
                created_at: NOW,
              },
            ]
          : [],
      ),
    ),
    http.get('/api/v1/claims/7/audit', () =>
      HttpResponse.json([
        {
          id: 1,
          entity_type: 'claim',
          entity_id: 7,
          action: 'claim.created',
          changes: {},
          actor_id: employee.id,
          created_at: NOW,
        },
      ]),
    ),
    http.get('/api/v1/claims/7/comments', () => HttpResponse.json([])),
    http.post('/api/v1/claims/7/reject', async ({ request }) => {
      rejectBody = await request.json()
      return HttpResponse.json({ ...claimFixture('REJECTED') })
    }),
  )
  return { rejectBody: () => rejectBody }
}

describe('claim detail page', () => {
  it('renders lines with policy verdicts and claim-level findings', async () => {
    setToken(`mock-token-${employee.id}`)
    mockClaim('PENDING_APPROVAL')
    renderRoute('/claims/7')

    expect(await screen.findByRole('heading', { name: 'Mumbai client visit' })).toBeVisible()
    expect(screen.getByText('Taj Lands End')).toBeInTheDocument()
    expect(screen.getByText(/Mumbai · 4 nights/)).toBeInTheDocument()
    expect(await screen.findByText(/exceeds tier-1 limit/)).toBeInTheDocument()
    expect(screen.getByText('Total above auto-approve limit')).toBeInTheDocument()
    // Owner of a pending claim: no review actions, no edit.
    expect(screen.queryByRole('button', { name: /Approve/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Edit claim/ })).not.toBeInTheDocument()
  })

  it('lets the assigned approver reject only with a comment', async () => {
    setToken(`mock-token-${manager.id}`)
    const calls = mockClaim('PENDING_APPROVAL')
    renderRoute('/claims/7')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /Reject/ }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }))
    expect(await within(dialog).findByText('A comment is required')).toBeInTheDocument()
    expect(calls.rejectBody()).toBeUndefined()

    await user.type(within(dialog).getByLabelText('Comment'), 'Not a business expense')
    await user.click(within(dialog).getByRole('button', { name: 'Reject' }))
    await waitFor(() =>
      expect(calls.rejectBody()).toEqual({ step_id: 41, comment: 'Not a business expense' }),
    )
  })

  it('shows Edit to the owner of a draft', async () => {
    setToken(`mock-token-${employee.id}`)
    mockClaim('DRAFT')
    renderRoute('/claims/7')
    expect(await screen.findByRole('link', { name: /Edit claim/ })).toHaveAttribute(
      'href',
      '/claims/7/edit',
    )
  })

  it('shows not found for a missing claim', async () => {
    setToken(`mock-token-${employee.id}`)
    server.use(
      http.get('/api/v1/claims/999', () =>
        HttpResponse.json({ detail: 'Claim not found' }, { status: 404 }),
      ),
    )
    renderRoute('/claims/999')
    expect(await screen.findByRole('heading', { name: 'Claim not found' })).toBeVisible()
  })
})
