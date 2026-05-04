// API Client for Maler Kostenvoranschlag


const resolvedBase = (import.meta.env && import.meta.env.VITE_API_BASE_URL) ? import.meta.env.VITE_API_BASE_URL : '';
const apiPrefix = resolvedBase ? '/api/v1' : '/api'
const API_BASE_URL = (resolvedBase || '') + apiPrefix;
const PUBLIC_API_BASE_URL = resolvedBase ? `${resolvedBase}/api/v1` : '/api';

class ApiClient {
  constructor() {
    // Entfernt: this.token = localStorage.getItem('access_token');
  }

  setToken(token) {
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }

  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...(options.headers || {}),
      },
    };

    // Wenn body ein FormData ist, entferne Content-Type (Browser setzt ihn automatisch)
    if (options.body instanceof FormData) {
      if (config.headers['Content-Type']) {
        delete config.headers['Content-Type'];
      }
    }

    const response = await fetch(url, config);

    if (!response.ok) {
      if (response.status === 401) {
        this.setToken(null);
        window.dispatchEvent(new Event('auth:logout'));
        throw new Error('Authentication required');
      }

      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  // Authentication
  async login(email, password) {
    const response = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (response.access_token) {
      this.setToken(response.access_token);
    }
    return response;
  }

  async demoLogin() {
    const response = await this.request('/auth/demo-login', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    if (response.access_token) {
      this.setToken(response.access_token);
    }
    return response;
  }

  async register(userData) {
    return await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async verifyEmail(token) {
    return await this.request(`/auth/verify-email?token=${encodeURIComponent(token)}`);
  }

  async resendVerification(email) {
    return await this.request('/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async logout() {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  }

  async getCurrentUser() {
    return await this.request('/auth/me');
  }

  async updateUserProfile(payload) {
    return await this.request('/users/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteUserLogo() {
    return await this.request('/onboarding/logo', { method: 'DELETE' });
  }

  // Quotes
  async getQuotes(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/quotes/?${queryString}` : '/quotes/';
    return await this.request(endpoint);
  }

  async createQuote(quoteData) {
    return await this.request('/quotes/', {
      method: 'POST',
      body: JSON.stringify(quoteData),
    });
  }

  async getQuote(quoteId) {
    return await this.request(`/quotes/${quoteId}`);
  }

  async updateQuote(quoteId, updateData) {
    return await this.request(`/quotes/${quoteId}`, {
      method: 'PUT',
      body: JSON.stringify(updateData),
    });
  }

  async deleteQuote(quoteId) {
    return await this.request(`/quotes/${quoteId}`, {
      method: 'DELETE',
    });
  }

  async generateQuoteWithAI(quoteId, projectDescription) {
    return await this.request(`/quotes/${quoteId}/generate-ai`, {
      method: 'POST',
      body: JSON.stringify({ project_description: projectDescription }),
    });
  }

  async duplicateQuote(quoteId) {
    return await this.request(`/quotes/${quoteId}/duplicate`, {
      method: 'POST',
    });
  }

  async updateQuoteStatus(quote, status) {
    return await this.updateQuote(quote.id, {
      customer_name: quote.customer_name || '-',
      customer_email: quote.customer_email || null,
      customer_phone: quote.customer_phone || null,
      customer_address: quote.customer_address || null,
      project_title: quote.project_title || 'Kostenvoranschlag',
      project_description: quote.project_description || '',
      total_amount: quote.total_amount || 0,
      status,
      created_by_ai: Boolean(quote.created_by_ai),
    });
  }

  // AI Services
  async analyzeProject(projectData) {
    return await this.request('/ai/analyze', {
      method: 'POST',
      body: JSON.stringify(projectData),
    });
  }

  async generateQuoteItems(projectDescription) {
    return await this.request('/ai/generate-quote', {
      method: 'POST',
      body: JSON.stringify({ project_description: projectDescription }),
    });
  }

  // Payments
  async createPaymentSession(quoteId) {
    return await this.request('/payments/create-session', {
      method: 'POST',
      body: JSON.stringify({ quote_id: quoteId }),
    });
  }

  async getPaymentStatus(sessionId) {
    return await this.request(`/payments/status/${sessionId}`);
  }

  // Unified Agent
  async chatWithAgent(message, attachments = []) {
    return await this.request('/agent/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        attachments,
        channel: 'web',
      }),
    });
  }

  getAgentPdfUrl(pdfUrl) {
    return this.getPublicApiUrl(pdfUrl);
  }

  getPublicApiUrl(pathOrUrl) {
    if (!pathOrUrl) return null;
    if (pathOrUrl.startsWith('http')) return pathOrUrl;
    const path = pathOrUrl.replace(/^\/api\/v1/, '');
    return `${PUBLIC_API_BASE_URL}${path}`;
  }

  async fetchAgentPdf(pdfUrl) {
    const url = this.getPublicApiUrl(pdfUrl);
    if (!url) throw new Error('PDF URL fehlt');
    return await this.fetchAuthenticatedBlob(url);
  }

  async fetchAgentPdfByQuoteId(quoteId) {
    const info = await this.request(`/quotes/${quoteId}/agent-pdf-info`);
    if (!info?.pdf_url) throw new Error('PDF URL fehlt');
    const blob = await this.fetchAgentPdf(info.pdf_url);
    return { blob, filename: info.pdf_filename };
  }

  // Telegram-Linking
  async getChannelLinks() {
    return await this.request('/agent/channel-links');
  }

  async createTelegramLinkingToken() {
    return await this.request('/agent/linking-token', {
      method: 'POST',
      body: JSON.stringify({}),
    });
  }

  // Onboarding
  async getOnboardingStatus() {
    return await this.request('/onboarding/status');
  }

  async completeOnboarding(payload) {
    return await this.request('/onboarding/complete', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async uploadLogo(file) {
    const form = new FormData();
    form.append('file', file);
    return await this.request('/onboarding/logo', {
      method: 'POST',
      body: form,
    });
  }

  async fetchAuthenticatedBlob(url) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(url, {
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    });
    if (!response.ok) throw new Error(`PDF download failed: ${response.status}`);
    return await response.blob();
  }

  // Health check
  async healthCheck() {
    const base = resolvedBase || 'http://localhost:8000'
    const response = await fetch(`${base}/health`)
    return await response.json()
  }

  // AI Analysis
  async analyzeInput(input) {
    const response = await this.request('/ai/analyze-project', {
      method: 'POST',
      body: JSON.stringify({ input }),
    });
    return response;
  }

  async askQuestion(question, conversationHistory) {
    const response = await this.request('/ai/ask-question', {
      method: 'POST',
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory
      }),
    });
    return response;
  }

  async generateQuoteFromConversation(data) {
    const response = await this.request('/ai/generate-quote', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response.data;
  }

  // Quick Quote (MVP)
  async createQuickQuote(data) {
    return await this.request('/ai/quick-quote', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async uploadDocument(formData) {
    return await this.request('/ai/upload-document', {
      method: 'POST',
      body: formData,
    });
  }

  async getDocumentStatus(documentId) {
    const response = await this.request(`/ai/document-status/${documentId}`);
    return response.data;
  }
}

// Create singleton instance
const apiClient = new ApiClient();

export default apiClient;

