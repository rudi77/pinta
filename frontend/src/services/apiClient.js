// API Client for Maler Kostenvoranschlag


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL + '/api';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('access_token');
  }

  setToken(token) {
    this.token = token;
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
    
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
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
          // Token expired or invalid
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
}

// Create singleton instance
const apiClient = new ApiClient();

export default apiClient;

