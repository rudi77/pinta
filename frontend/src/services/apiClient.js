// API Client for Maler Kostenvoranschlag


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL + '/api';

class ApiClient {
  constructor() {
    // Entfernt: this.token = localStorage.getItem('access_token');
  }

  setToken(token) {
    console.log('setToken called with:', token);
    if (token) {
      localStorage.setItem('access_token', token);
      console.log('Token saved to localStorage:', token);
    } else {
      localStorage.removeItem('access_token');
      console.log('Token removed from localStorage');
    }
  }

  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('access_token');
    console.log('TOKEN IM HEADER:', token);
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

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        if (response.status === 401) {
          console.warn('401 Unauthorized! Token wird entfernt.', { url, config });
          this.setToken(null);
          window.dispatchEvent(new Event('auth:logout'));
          throw new Error('Authentication required');
        }
        
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Authentication
  async login(email, password) {
    const response = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    console.log('LOGIN RESPONSE:', response);
    if (response.access_token) {
      console.log('SET TOKEN:', response.access_token);
      this.setToken(response.access_token);
    } else {
      console.warn('NO ACCESS TOKEN IN LOGIN RESPONSE');
    }
    return response;
  }

  async register(userData) {
    console.log('BEFORE REGISTER RESPONSE');
    const response = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
    console.log('REGISTER RESPONSE:', response);
    return response;
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

  // Quotes
  async getQuotes(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const endpoint = queryString ? `/quotes?${queryString}` : '/quotes';
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

  // Health check
  async healthCheck() {
    const response = await fetch('http://localhost:8000/health');
    return await response.json();
  }

  // AI Analysis
  async analyzeInput(input) {
    const response = await this.request('/ai/analyze-input', {
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

  async generateQuoteWithAI(data) {
    const response = await this.request('/ai/generate-quote', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response.data;
  }

  async uploadDocument(formData) {
    const response = await this.request('/ai/upload-document', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  }

  async getDocumentStatus(documentId) {
    const response = await this.request(`/ai/document-status/${documentId}`);
    return response.data;
  }
}

// Create singleton instance
const apiClient = new ApiClient();

export default apiClient;

