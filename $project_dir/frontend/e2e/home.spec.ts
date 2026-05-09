import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" the project name.
  await expect(page).toHaveTitle(/phase2_showcase/);
});

test('dashboard welcomes user', async ({ page }) => {
  await page.goto('/');

  // Expects page to have a heading with the project name
  await expect(page.getByText('Welcome to your phase2_showcase dashboard')).toBeVisible();
});
