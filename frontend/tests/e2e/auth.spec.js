import { expect, test } from '@playwright/test';
import { mockDemoLogin } from './helpers/apiMocks.js';

test.describe('authentication shell', () => {
  for (const route of ['/dashboard', '/chat-quote', '/quick-quote', '/new-quote']) {
    test(`${route} redirects unauthenticated users to login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByRole('heading', { name: 'Anmelden' })).toBeVisible();
    });
  }

  test('login and register pages link to each other', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Noch kein Konto? Registrieren' }).click();
    await expect(page).toHaveURL(/\/register$/);
    await expect(page.getByRole('heading', { name: 'Registrieren' })).toBeVisible();

    await page.getByRole('button', { name: 'Bereits ein Konto? Anmelden' }).click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('demo login uses a real token path and lands in the agent chat', async ({ page }) => {
    await mockDemoLogin(page);

    await page.goto('/login');
    await page.getByRole('button', { name: 'Demo-Modus' }).click();

    await expect(page).toHaveURL(/\/chat-quote$/);
    await expect(page.getByPlaceholder('Beschreiben Sie Ihr Projekt...')).toBeVisible();
    await expect(page.evaluate(() => window.localStorage.getItem('access_token'))).resolves.toBe('demo-access-token');
  });
});
