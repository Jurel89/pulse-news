import { expect, test } from '@playwright/test';

test('bootstrap and dashboard flow', async ({ page }) => {
  await page.goto('/');

  if (await page.getByRole('heading', { name: /create the first operator account/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /create operator account/i }).click();
  } else {
    await expect(page.getByRole('heading', { name: /log in to pulse news/i })).toBeVisible();
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }

  await expect(page.getByRole('heading', { name: /run dashboard/i })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Jobs' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Logs' })).toBeVisible();
});
