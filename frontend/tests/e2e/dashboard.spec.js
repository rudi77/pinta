import { expect, test } from '@playwright/test';
import {
  mockAuthenticatedUser,
  mockDashboardQuotes,
  mockEmptyDashboard,
  mockQuoteDetail,
  sampleQuote,
} from './helpers/apiMocks.js';

test.describe('dashboard navigation', () => {
  test('empty dashboard shows a single CTA that opens the quote chat', async ({ page }) => {
    await mockAuthenticatedUser(page, {
      id: 2,
      username: 'mvp-user',
      email: 'mvp@example.com',
      company_name: 'MVP Malerbetrieb',
      is_premium: true,
    });
    await mockEmptyDashboard(page);

    await page.goto('/dashboard');
    await expect(page.getByText('Noch keine Angebote erstellt.')).toBeVisible();

    await page.getByRole('button', { name: 'Erstes Angebot erstellen' }).click();
    await expect(page).toHaveURL(/\/quote\/new$/);
  });

  test('main "Neues Angebot starten" button opens the quote chat', async ({ page }) => {
    await mockAuthenticatedUser(page, {
      id: 2,
      username: 'mvp-user',
      email: 'mvp@example.com',
      company_name: 'MVP Malerbetrieb',
      is_premium: true,
    });
    await mockEmptyDashboard(page);

    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Neues Angebot starten' }).click();
    await expect(page).toHaveURL(/\/quote\/new$/);
  });

  test('quote rows open quote details', async ({ page }) => {
    await mockAuthenticatedUser(page, {
      id: 2,
      username: 'mvp-user',
      email: 'mvp@example.com',
      company_name: 'MVP Malerbetrieb',
      is_premium: true,
    });
    await mockDashboardQuotes(page);
    await mockQuoteDetail(page);

    await page.goto('/dashboard');
    await page.getByRole('row', { name: new RegExp(sampleQuote.quote_number) }).click();

    await expect(page).toHaveURL(/\/quotes\/42$/);
    await expect(page.getByRole('heading', { name: `Angebot ${sampleQuote.quote_number}` })).toBeVisible();
  });
});
