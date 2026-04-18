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

  // Clean up any pre-existing ChatGPT OAuth connection so the test starts
  // from a known empty state even on a reused database.
  await page.evaluate(async () => {
    const resp = await fetch('/api/api-keys', { credentials: 'include' });
    const keys = await resp.json();
    const oauthKey = keys.find((k: any) => k.provider_type === 'openai_chatgpt' && k.auth_type === 'oauth');
    if (oauthKey) {
      await fetch(`/api/oauth/openai/${oauthKey.id}`, { method: 'DELETE', credentials: 'include' });
    }
  });

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

  // OAuth connect prompt should appear with a clickable link
  const oauthPrompt = page.locator('.form-info');
  await expect(oauthPrompt).toBeVisible();
  await expect(oauthPrompt).toContainText('uses OAuth');

  // Clicking the connect link should open the device-auth modal
  await oauthPrompt.locator('a').click();
  const modal = page.locator('.modal-panel');
  await expect(modal).toBeVisible();
  // The modal title should reference ChatGPT / device connection
  await expect(modal).toContainText('ChatGPT');

  await expect(modal).toContainText('Waiting for you to authorise');

  // Wait past the first poll interval. OpenAI typically returns interval=5s;
  // waiting 8s ensures the backend has polled at least once. After the fix,
  // a 403 deviceauth_authorization_unknown response is treated as pending,
  // so the modal must remain usable instead of falling into an error state.
  await page.waitForTimeout(8000);
  await expect(modal).toBeVisible();
  await expect(modal.locator('.error-banner')).not.toBeVisible();
  const waitingText = modal.locator('p').filter({ hasText: /Waiting for you to authorise|Checking for authorisation/ });
  await expect(waitingText).toBeVisible();

  // The default model should not be a codex model
  const defaultModelInput = page.locator('input[list="provider-model-options"]');
  const defaultValue = await defaultModelInput.inputValue();
  expect(defaultValue).not.toContain('codex');
  expect(defaultValue).toMatch(/^gpt-5\./);
});
