import { expect, test } from '@playwright/test';
import { mockDemoLogin } from './helpers/apiMocks.js';

test.describe('authentication shell', () => {
  for (const route of ['/dashboard', '/quote/new', '/quick-quote']) {
    test(`${route} redirects unauthenticated users to login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByRole('heading', { name: 'Anmelden' })).toBeVisible();
    });
  }

  test('legacy /chat-quote and /new-quote redirect to /quote/new (then login)', async ({ page }) => {
    await page.goto('/chat-quote');
    await expect(page).toHaveURL(/\/login$/);

    await page.goto('/new-quote');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('login and register pages link to each other', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Noch kein Konto? Registrieren' }).click();
    await expect(page).toHaveURL(/\/register$/);
    await expect(page.getByRole('heading', { name: 'Registrieren' })).toBeVisible();

    await page.getByRole('button', { name: 'Bereits ein Konto? Anmelden' }).click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('demo login lands on dashboard (onboarding skipped for demo)', async ({ page }) => {
    await mockDemoLogin(page);

    await page.goto('/login');
    await page.getByRole('button', { name: 'Demo-Modus' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.evaluate(() => window.localStorage.getItem('access_token'))).resolves.toBe('demo-access-token');
  });
});
