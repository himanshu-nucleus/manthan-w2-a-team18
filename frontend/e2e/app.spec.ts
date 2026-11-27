import { expect, test } from '@playwright/test'

test('home page renders and counter increments', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'manthan-w2-a-team18' })).toBeVisible()
  await page.getByRole('button', { name: /count is 0/i }).click()
  await expect(page.getByRole('button', { name: /count is 1/i })).toBeVisible()
})
