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

    if (!bootstrapResult.ok) {
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
        `Bootstrap failed (${bootstrapResult.status} ${bootstrapResult.body}) and login fallback also failed (${loginResult.status} ${loginResult.body})`,
      ).toBe(true);
    }
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

test('chatgpt subscription preset shows oauth prompt and non-codex default model', async ({ page }) => {
  await ensureAuthenticated(page);

  await page.getByRole('button', { name: 'Providers' }).click();
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: 'New Provider' }).click();
  await page.waitForLoadState('networkidle');

  const presetSelect = page.locator('select').first();
  await presetSelect.waitFor({ state: 'visible', timeout: 15000 });
  await expect(presetSelect).toBeEnabled();
  await presetSelect.selectOption('openai_chatgpt');

  // The provider type input should be auto-filled
  await expect(page.locator('input[placeholder="openai"]')).toHaveValue('openai_chatgpt');

  // No API-key warning should appear for an OAuth-backed preset
  await expect(page.locator('.form-error')).not.toBeVisible();

  // OAuth connect prompt should appear
  const oauthPrompt = page.locator('.form-info');
  await expect(oauthPrompt).toBeVisible();
  await expect(oauthPrompt).toContainText('uses OAuth');

  // The default model should not be a codex model
  const defaultModelInput = page.locator('input[list="provider-model-options"]');
  const defaultValue = await defaultModelInput.inputValue();
  expect(defaultValue).not.toContain('codex');
  expect(defaultValue).toMatch(/^gpt-5\./);
});
