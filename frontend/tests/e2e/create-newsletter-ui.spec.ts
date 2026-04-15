import { expect, test, type Page } from '@playwright/test';

const E2E_EMAIL = process.env.PLAYWRIGHT_E2E_EMAIL ?? 'operator@example.com';
const E2E_PASSWORD = process.env.PLAYWRIGHT_E2E_PASSWORD ?? 'super-secret-password';

type SessionPayload = {
  initialized: boolean;
  authenticated: boolean;
};

async function ensureAuthenticated(page: Page): Promise<void> {
  await page.goto('/');

  const session = await page.evaluate(async () => {
    const response = await fetch('/api/auth/session', { credentials: 'include' });
    return (await response.json()) as SessionPayload;
  });

  if (!session.initialized) {
    const bootstrapResult = await page.evaluate(
      async ({ email, password }) => {
        const response = await fetch('/api/auth/bootstrap', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        });
        return { ok: response.ok, status: response.status, body: await response.text() };
      },
      { email: E2E_EMAIL, password: E2E_PASSWORD },
    );

    expect(bootstrapResult.ok, `Bootstrap failed: ${bootstrapResult.status} ${bootstrapResult.body}`).toBe(true);
  } else if (!session.authenticated) {
    const loginResult = await page.evaluate(
      async ({ email, password }) => {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        });
        return { ok: response.ok, status: response.status, body: await response.text() };
      },
      { email: E2E_EMAIL, password: E2E_PASSWORD },
    );

    expect(
      loginResult.ok,
      `Login failed for PLAYWRIGHT_E2E_EMAIL=${E2E_EMAIL}: ${loginResult.status} ${loginResult.body}`,
    ).toBe(true);
  }

  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });
}

async function ensureNewslettersNav(page: import('@playwright/test').Page) {
  await page.waitForLoadState('networkidle');
  if (await page.getByRole('button', { name: 'Newsletters' }).count()) {
    return;
  }

  await page.reload();
  await ensureAuthenticated(page);
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('button', { name: 'Newsletters' })).toBeVisible({ timeout: 15000 });
}

test('newsletters page exposes newsletter creation controls', async ({ page }) => {
  await ensureAuthenticated(page);

  await ensureNewslettersNav(page);
  await page.getByRole('button', { name: 'Newsletters' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('button', { name: /new newsletter/i })).toBeVisible({ timeout: 15000 });
});
