import { expect, test } from '@playwright/test';
import { mockAgentPdf, mockAgentQuote, mockAuthenticatedUser } from './helpers/apiMocks.js';

test.describe('agent quote chat', () => {
  test('sends a message to the unified agent and surfaces quote actions', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockAgentQuote(page);
    let pdfAuthorizationHeader = null;
    await mockAgentPdf(page, (request) => {
      pdfAuthorizationHeader = request.headers().authorization;
    });

    await page.goto('/chat-quote');
    await page.getByPlaceholder('Beschreiben Sie Ihr Projekt...').fill(
      'Wohnzimmer 25 m2 weiss streichen, Decke mitmachen.',
    );
    await page.keyboard.press('Enter');

    await expect(page.getByText('Wohnzimmer 25 m2 weiss streichen')).toBeVisible();
    await expect(page.getByText('Kostenvoranschlag fertig. PDF kommt gleich.')).toBeVisible();
    await expect(page.getByText('Angebot KV-20260503-201500-demo42 ist fertig.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'PDF öffnen' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Angebot anzeigen' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Im Dashboard anzeigen' })).toBeVisible();

    await page.getByRole('button', { name: 'PDF öffnen' }).first().click();
    await expect.poll(() => pdfAuthorizationHeader).toBe('Bearer test-access-token');
  });
});
