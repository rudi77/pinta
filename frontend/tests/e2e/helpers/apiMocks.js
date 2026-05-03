export const demoUser = {
  id: 1,
  username: 'demo',
  email: 'demo@example.com',
  company_name: 'Demo Malerbetrieb',
  is_premium: true,
};

export const sampleQuote = {
  id: 42,
  quote_number: 'KV-20260503-201500-demo42',
  user_id: 1,
  customer_name: 'Familie Schmidt',
  customer_email: 'schmidt@example.com',
  customer_phone: '+49123456789',
  customer_address: 'Musterstrasse 1, 10115 Berlin',
  project_title: 'Schlafzimmer streichen',
  project_description: 'Schlafzimmer mit Decke weiss streichen.',
  total_amount: 1953.08,
  status: 'draft',
  created_by_ai: true,
  is_paid: false,
  created_at: '2026-05-03T18:46:28Z',
  updated_at: '2026-05-03T18:46:28Z',
  items: [
    {
      id: 1,
      quote_id: 42,
      position: 1,
      description: 'Malerarbeiten Schlafzimmer',
      quantity: 21.53,
      unit: 'h',
      unit_price: 58,
      total_price: 1248.74,
      created_at: '2026-05-03T18:46:28Z',
      updated_at: '2026-05-03T18:46:28Z',
    },
  ],
};

export async function mockAuthenticatedUser(page, user = demoUser) {
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'test-access-token');
  });
  await page.route(/\/api(\/v1)?\/auth\/me$/, async (route) => {
    await route.fulfill({ json: user });
  });
}

export async function mockDemoLogin(page, user = demoUser) {
  await page.route(/\/api(\/v1)?\/auth\/demo-login$/, async (route) => {
    await route.fulfill({
      json: {
        access_token: 'demo-access-token',
        refresh_token: 'demo-refresh-token',
        token_type: 'bearer',
      },
    });
  });
  await page.route(/\/api(\/v1)?\/auth\/me$/, async (route) => {
    await route.fulfill({ json: user });
  });
}

export async function mockEmptyDashboard(page) {
  await page.route(/\/api(\/v1)?\/quotes\/\?limit=10$/, async (route) => {
    await route.fulfill({ json: [] });
  });
}

export async function mockDashboardQuotes(page, quotes = [sampleQuote]) {
  await page.route(/\/api(\/v1)?\/quotes\/\?limit=10$/, async (route) => {
    await route.fulfill({ json: quotes });
  });
}

export async function mockQuoteDetail(page, quote = sampleQuote) {
  await page.route(new RegExp(`/api(/v1)?/quotes/${quote.id}$`), async (route) => {
    await route.fulfill({ json: quote });
  });
}

export async function mockQuotePdfGenerate(page, quoteId = sampleQuote.id, onRequest = () => {}) {
  await page.route(new RegExp(`/api(/v1)?/quotes/${quoteId}/pdf/generate$`), async (route) => {
    onRequest(route.request());
    await route.fulfill({
      json: {
        success: true,
        message: 'PDF generated successfully',
        pdf_info: {
          success: true,
          pdf_base64: 'JVBERi0xLjQKJSBkZW1vIHBkZgo=',
        },
      },
    });
  });
}

export async function mockQuickQuote(page, quote = sampleQuote) {
  await page.route(/\/api(\/v1)?\/ai\/quick-quote$/, async (route) => {
    const requestBody = route.request().postDataJSON();
    if (!requestBody.service_description) {
      throw new Error('Quick quote request must include a service description.');
    }
    await route.fulfill({
      json: {
        quote_id: quote.id,
        quote_number: quote.quote_number,
        project_title: quote.project_title,
        items: quote.items.map((item) => ({
          position: item.position,
          description: item.description,
          quantity: item.quantity,
          unit: item.unit,
          unit_price: item.unit_price,
          total_price: item.total_price,
          category: 'labor',
        })),
        subtotal: 1641.24,
        vat_amount: 311.84,
        total_amount: quote.total_amount,
        notes: 'Annahmen: Standardraumhöhe, zwei Anstriche.',
        recommendations: ['Untergrund vor Ort prüfen.'],
      },
    });
  });
}

export async function mockDuplicateQuote(page, quote = sampleQuote) {
  const duplicatedQuote = {
    ...quote,
    id: 43,
    quote_number: 'KV-20260503-201501-copy43',
    project_title: `Kopie - ${quote.project_title}`,
  };
  await page.route(new RegExp(`/api(/v1)?/quotes/${quote.id}/duplicate$`), async (route) => {
    await route.fulfill({
      json: duplicatedQuote,
    });
  });
  await page.route(new RegExp(`/api(/v1)?/quotes/${duplicatedQuote.id}$`), async (route) => {
    await route.fulfill({ json: duplicatedQuote });
  });
}

export async function mockUpdateQuoteStatus(page, quote = sampleQuote) {
  await page.route(new RegExp(`/api(/v1)?/quotes/${quote.id}$`), async (route) => {
    if (route.request().method() !== 'PUT') {
      await route.fallback();
      return;
    }
    const requestBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        ...quote,
        status: requestBody.status,
      },
    });
  });
}

export async function mockAgentQuote(page) {
  await page.route(/\/api(\/v1)?\/agent\/chat$/, async (route) => {
    const requestBody = route.request().postDataJSON();
    if (!requestBody.message) {
      throw new Error('Agent chat request must include a message.');
    }
    await route.fulfill({
      json: {
        conversation_id: 7,
        final_message: 'Kostenvoranschlag fertig. PDF kommt gleich.',
        humanized_message: 'Kostenvoranschlag fertig. PDF kommt gleich.',
        pdf_url: '/api/v1/agent/pdf/demo-quote.pdf',
        pdf_filename: 'demo-quote.pdf',
        quote_id: 42,
        quote_number: 'KV-20260503-201500-demo42',
        status: 'completed',
      },
    });
  });
}

export async function mockAgentPdf(page, onRequest = () => {}) {
  await page.route(/\/api(\/v1)?\/agent\/pdf\/demo-quote\.pdf$/, async (route) => {
    onRequest(route.request());
    await route.fulfill({
      contentType: 'application/pdf',
      body: '%PDF-1.4\n% demo pdf\n',
    });
  });
}
