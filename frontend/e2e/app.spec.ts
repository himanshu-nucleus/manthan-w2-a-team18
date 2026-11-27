import { expect, test } from '@playwright/test'

// Runs against the MSW mocks (playwright.config.ts sets VITE_ENABLE_MOCKS=true).

test('signed-out visitor is sent to the login page', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: 'Sign in to your account' })).toBeVisible()
})

test('wrong password shows an error and keeps the email', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Work email').fill('employee@expenseflow.example')
  await page.getByLabel('Password').fill('wrong')
  await page.getByLabel('Password').press('Enter')
  await expect(page.getByText('Email or password is incorrect.')).toBeVisible()
  await expect(page.getByLabel('Work email')).toHaveValue('employee@expenseflow.example')
  await expect(page.getByLabel('Password')).toHaveValue('')
})

test('employee signs in, survives a reload and signs out', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Work email').fill('employee@expenseflow.example')
  await page.getByLabel('Password').fill('password')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByText('Signed in as employee@expenseflow.example')).toBeVisible()

  await page.reload()
  await expect(page.getByText('Signed in as employee@expenseflow.example')).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
})
