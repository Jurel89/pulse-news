import { expect, test } from '@playwright/test';

async function ensureJobsNav(page: import('@playwright/test').Page) {
  await page.waitForLoadState('networkidle');
  if (await page.getByRole('button', { name: 'Jobs' }).count()) {
    return;
  }

  await page.reload();
  if (await page.getByRole('heading', { name: /log in to pulse news/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('button', { name: 'Jobs' })).toBeVisible({ timeout: 15000 });
}

test('jobs page exposes newsletter creation controls', async ({ page }) => {
  await page.goto('/');

  if (await page.getByRole('heading', { name: /create the first operator account/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /create operator account/i }).click();
  } else {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }

  await ensureJobsNav(page);
  await page.getByRole('button', { name: 'Jobs' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('button', { name: /new newsletter/i })).toBeVisible({ timeout: 15000 });
});
