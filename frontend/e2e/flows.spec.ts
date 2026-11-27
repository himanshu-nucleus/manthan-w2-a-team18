import { expect, type Page, test } from '@playwright/test'

// End-to-end flows against the MSW mocks (playwright.config.ts sets VITE_ENABLE_MOCKS=true).
// The mock store lives in page memory, so in-app navigation (not page.goto) is used after
// a mutation whenever the next screen must see it.

async function login(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel('Work email').fill(email)
  await page.getByLabel('Password').fill('password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

const nav = (page: Page) => page.getByRole('navigation', { name: 'Main' })

test.describe('on a phone (375px)', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('employee creates a draft claim and sees it in My claims', async ({ page }) => {
    await login(page, 'employee@expenseflow.example')
    await page.goto('/claims/new')
    await page.getByLabel('Claim title').fill('E2E taxi to client')
    await page.getByLabel('Category').selectOption('cab')
    await page.getByLabel('Amount (₹)').fill('320')
    await page.getByRole('button', { name: 'Save draft' }).click()
    await expect(page.getByText('Draft saved')).toBeVisible()
    await expect(page).toHaveURL(/\/claims\/\d+\/edit$/)

    // Client-side navigation keeps the in-memory mock store.
    await nav(page).getByRole('link', { name: 'My claims' }).click()
    await expect(page).toHaveURL(/\/claims$/)
    await expect(page.getByText('E2E taxi to client').first()).toBeVisible()
  })

  test('hotel line without city and nights cannot be submitted', async ({ page }) => {
    await login(page, 'employee@expenseflow.example')
    await page.goto('/claims/new')
    await page.getByLabel('Claim title').fill('Hotel without details')
    await page.getByLabel('Category').selectOption('hotel')
    await page.getByLabel('Amount (₹)').fill('400')
    await page.getByLabel('Expense date').fill('2026-11-20')
    await page.getByLabel('Vendor').fill('Lemon Tree')
    await page.getByRole('button', { name: 'Submit claim' }).click()
    await expect(page.getByText('City is required for hotel stays')).toBeVisible()
    await expect(page.getByText('Nights are required for hotel stays')).toBeVisible()
    await expect(page).toHaveURL(/\/claims\/new$/)
  })
})

test('line above ₹500 without a receipt cannot be submitted', async ({ page }) => {
  await login(page, 'employee@expenseflow.example')
  await page.goto('/claims/new')
  await page.getByLabel('Claim title').fill('Dinner with client')
  await page.getByLabel('Category').selectOption('meal')
  await page.getByLabel('Amount (₹)').fill('1200')
  await page.getByLabel('Expense date').fill('2026-11-20')
  await page.getByLabel('Vendor').fill('Barbeque Nation')
  await page.getByRole('button', { name: 'Submit claim' }).click()
  await expect(
    page.getByText('Receipt number and receipt file are required above ₹500').first(),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/claims\/new$/)
})

test('manager bulk-approves selected claims from the approvals queue', async ({ page }) => {
  await login(page, 'manager@expenseflow.example')
  await page.goto('/approvals')
  const row = (title: string) => page.getByRole('row').filter({ hasText: title })
  await row('Team lunch').getByRole('checkbox').click()
  await row('Airport cab').getByRole('checkbox').click()

  const bar = page.getByRole('region', { name: 'Bulk actions' })
  await expect(bar).toContainText('2 claims selected')
  await bar.getByRole('button', { name: 'Approve 2' }).click()

  await expect(page.getByText('Approved 2 of 2')).toBeVisible()
  await expect(row('Team lunch')).toHaveCount(0)
  await expect(row('Airport cab')).toHaveCount(0)
  await expect(row('Client visit Pune')).toHaveCount(1)
})

test('manager must give a comment to send a claim back (claim detail)', async ({
  page,
  context,
}) => {
  // The MSW mocks have no approval-steps / send-back handlers yet; stub them here.
  const step = {
    id: 501,
    claim_id: 2,
    round: 1,
    step_order: 1,
    approver_role: 'line_manager',
    assigned_approver_id: null,
    status: 'PENDING',
    acted_by_id: null,
    on_behalf_of_id: null,
    acted_at: null,
    comment: null,
    created_at: '2026-11-21T10:00:00Z',
  }
  let sentBack: { comment?: string } | null = null
  let claimJson: Record<string, unknown> | null = null
  page.on('response', async (res) => {
    if (/\/api\/v1\/claims\/2$/.test(res.url()) && res.ok()) claimJson = await res.json()
  })
  await context.route('**/api/v1/claims/2/approval-steps', (route) =>
    route.fulfill({ json: [step] }),
  )
  await context.route('**/api/v1/claims/2/policy-results', (route) => route.fulfill({ json: [] }))
  await context.route('**/api/v1/claims/2/comments', (route) => route.fulfill({ json: [] }))
  await context.route('**/api/v1/claims/2/send-back', async (route) => {
    sentBack = route.request().postDataJSON()
    await route.fulfill({ json: { ...claimJson, status: 'SENT_BACK' } })
  })

  await login(page, 'manager@expenseflow.example')
  await page.goto('/claims/2')
  await page.getByRole('button', { name: 'Send back' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Send back for clarification')).toBeVisible()
  await dialog.getByRole('button', { name: 'Send back' }).click()
  await expect(dialog.getByRole('alert')).toHaveText('A comment is required')
  expect(sentBack).toBeNull()

  await dialog.getByLabel('Comment').fill('Please attach the hotel invoice.')
  await dialog.getByRole('button', { name: 'Send back' }).click()
  await expect(page.getByText('Claim sent back to the employee')).toBeVisible()
  expect(sentBack).toMatchObject({ step_id: 501, comment: 'Please attach the hotel invoice.' })
})

test('finance head edits a policy rule limit', async ({ page }) => {
  await login(page, 'admin@expenseflow.example')
  await page.goto('/admin/policy-rules')
  await page.getByRole('button', { name: 'Edit Meals up to 1,500 INR per day' }).click()

  const sheet = page.getByRole('dialog')
  await expect(sheet.getByText('Edit rule')).toBeVisible()
  await sheet.getByLabel('Limit').fill('1800')
  await sheet.getByRole('button', { name: 'Save rule' }).click()

  await expect(
    page.getByText(/^Saved ".*"\. Pending claims keep their earlier evaluation\.$/),
  ).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: 'MEAL_DAILY_LIMIT' })).toContainText(
    'Limit: 1800',
  )
})

test('finance head adds a person; employee cannot open People', async ({ browser }) => {
  const adminContext = await browser.newContext()
  const admin = await adminContext.newPage()
  await login(admin, 'admin@expenseflow.example')
  await admin.goto('/admin/people')
  await admin.getByRole('button', { name: 'Add person' }).click()

  const dialog = admin.getByRole('dialog')
  await dialog.getByLabel('Full name').fill('Priya Raman')
  await dialog.getByLabel('Work email').fill('priya.raman@expenseflow.example')
  await expect(dialog.getByLabel('Username')).toHaveValue('priya.raman@expenseflow.example')
  await dialog.getByLabel('Temporary password').fill('welcome123')
  await dialog.getByRole('button', { name: 'Add person' }).click()

  await expect(admin.getByText('Added Priya Raman.', { exact: false })).toBeVisible()
  await expect(admin.getByRole('row').filter({ hasText: 'Priya Raman' })).toBeVisible()
  await adminContext.close()

  const employeeContext = await browser.newContext()
  const employee = await employeeContext.newPage()
  await login(employee, 'employee@expenseflow.example')
  await employee.goto('/admin/people')
  await expect(employee.getByText('Only the finance head can manage people')).toBeVisible()
  await expect(employee.getByRole('button', { name: 'Add person' })).toHaveCount(0)
  await employeeContext.close()
})
