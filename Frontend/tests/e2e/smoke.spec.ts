import { test, expect } from '@playwright/test';

test.describe.skip(!process.env.E2E_BASE_URL, 'Set E2E_BASE_URL to run e2e', () => {
  test('loads dashboard shell', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/whales|\/$/);
  });
});
