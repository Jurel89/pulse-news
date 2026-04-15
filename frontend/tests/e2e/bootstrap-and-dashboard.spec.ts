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

test('bootstrap and dashboard flow', async ({ page }) => {
  await ensureAuthenticated(page);

  await expect(page.getByRole('heading', { name: /run dashboard/i })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Newsletters' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Logs' })).toBeVisible();
});

test('provider dropdown actions open and execute', async ({ page }) => {
  await ensureAuthenticated(page);

  await page.getByRole('button', { name: 'Providers' }).click();
  await page.waitForLoadState('networkidle');

  const actionTrigger = page.locator('button.action-dropdown-trigger').first();
  await expect(actionTrigger).toBeVisible({ timeout: 15000 });

  await actionTrigger.click();
  const disableAction = page.locator('button.action-dropdown-item').filter({ hasText: 'Disable' }).first();
  await expect(disableAction).toBeVisible({ timeout: 15000 });
  await disableAction.click();
  await expect(page.getByText(/provider updated|disabled|enabled/i).first()).toBeVisible({ timeout: 15000 });

  await actionTrigger.click();
  const enableAction = page.locator('button.action-dropdown-item').filter({ hasText: 'Enable' }).first();
  await expect(enableAction).toBeVisible({ timeout: 15000 });
  await enableAction.click();
  await expect(page.getByText(/provider updated|enabled/i).first()).toBeVisible({ timeout: 15000 });
});

test('api key action buttons toggle active state', async ({ page }) => {
  await ensureAuthenticated(page);

  await page.getByRole('button', { name: 'API Keys' }).click();
  await page.waitForLoadState('networkidle');

  const actionButtons = page.locator('.card-actions button');
  await expect(actionButtons.first()).toBeVisible({ timeout: 15000 });

  const toggleButton = actionButtons.nth(1);
  const initialLabel = (await toggleButton.textContent())?.trim();
  await toggleButton.click();
  await expect(page.getByText(/api key updated|activated|deactivated/i).first()).toBeVisible({ timeout: 15000 });

  const toggledLabel = (await actionButtons.nth(1).textContent())?.trim();
  expect(toggledLabel).not.toBe(initialLabel);

  await actionButtons.nth(1).click();
  await expect(page.getByText(/api key updated|activated|deactivated/i).first()).toBeVisible({ timeout: 15000 });
  await expect(actionButtons.nth(1)).toHaveText(initialLabel ?? '', { timeout: 15000 });
});
