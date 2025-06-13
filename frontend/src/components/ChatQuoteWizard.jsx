import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Loader2, Send, Upload, FileText } from 'lucide-react';

const ChatQuoteWizard = ({ onNavigate }) => {
  const { user, demoMode, isAuthenticated, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [conversationHistory, setConversationHistory] = useState([]);
  const [currentQuote, setCurrentQuote] = useState(null);
  const [showQuoteButton, setShowQuoteButton] = useState(false);
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const [customerData, setCustomerData] = useState({
    customer_name: '',
    customer_address: '',
    customer_email: '',
    customer_phone: ''
  });
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      // Debug: Log File-Objekt
      console.log('File-Objekt:', file);

      // Debug: Log FormData Inhalt
      const formData = new FormData();
      formData.append('file', file);
      if (currentQuote && currentQuote.quote && currentQuote.quote.id) {
        formData.append('quote_id', currentQuote.quote.id);
      }

      // Debug: Alle FormData-Einträge loggen
      for (let pair of formData.entries()) {
        console.log('FormData:', pair[0], pair[1]);
      }

      // Debug: Zeige Typ und Größe der Datei
      console.log('Dateityp:', file.type, 'Dateigröße:', file.size);

      // Upload file
      const response = await apiClient.uploadDocument(formData);

      // Dokument und Analyse im State speichern
      setUploadedDocuments(prev => [...prev, response]);

      // Add AI response to chat (mit Analyse-Feedback)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.analysis_result && response.analysis_result.extracted_text
          ? `Dokument analysiert: ${response.analysis_result.extracted_text}`
          : 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
        type: 'text',
        analysis: response.analysis_result
      }]);

      // Update conversation history
      setConversationHistory(prev => [...prev, {
        role: 'user',
        content: `Datei hochgeladen: ${file.name}`,
        timestamp: new Date().toISOString()
      }, {
        role: 'assistant',
        content: response.analysis_result && response.analysis_result.extracted_text
          ? `Dokument analysiert: ${response.analysis_result.extracted_text}`
          : 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
        timestamp: new Date().toISOString()
      }]);

    } catch (err) {
      console.error('Failed to upload file:', err);
      setError('Fehler beim Hochladen der Datei: ' + (err.message || 'Unbekannter Fehler'));
      // Add error message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, beim Hochladen der Datei ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      // Add user message to chat
      setMessages(prev => [...prev, {
        role: 'user',
        content: userMessage,
        type: 'text'
      }]);

      // Update conversation history
      const updatedHistory = [...conversationHistory, {
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString()
      }];
      setConversationHistory(updatedHistory);

      // If this is the first message, analyze input
      if (messages.length === 0) {
        const analysis = await apiClient.analyzeInput(userMessage);
        console.log('AI analysis response:', analysis);
        // Sicherstellen, dass questions existiert und mindestens ein Element hat
        const firstQuestion = analysis?.questions?.[0]?.question || 'Keine Frage generiert.';
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: firstQuestion,
          type: 'text'
        }]);

        // Update conversation history
        setConversationHistory(prev => [...prev, {
          role: 'assistant',
          content: firstQuestion,
          timestamp: new Date().toISOString()
        }]);

      } else {
        // Process follow-up question
        const response = await apiClient.askQuestion(userMessage, updatedHistory);
        
        // Add AI response to chat
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.response,
          type: 'text'
        }]);

        // Update conversation history
        setConversationHistory(prev => [...prev, {
          role: 'assistant',
          content: response.response,
          timestamp: new Date().toISOString()
        }]);

        // If we have enough information, show quote button
        if (!response.needs_more_info) {
          setShowQuoteButton(true);
        }
      }

    } catch (err) {
      console.error('Failed to process message:', err);
      setError('Fehler bei der Verarbeitung: ' + (err.message || 'Unbekannter Fehler'));
      
      // Add error message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleShowCustomerForm = () => {
    setShowCustomerForm(true);
  };

  const handleCustomerInputChange = (e) => {
    const { name, value } = e.target;
    setCustomerData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCustomerFormSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // Sammle alle Analyse-Resultate der hochgeladenen Dokumente
      const documentAnalyses = uploadedDocuments
        .map(doc => doc.analysis_result)
        .filter(Boolean);
      // Generate quote with customer data and document analyses
      const quoteData = await apiClient.generateQuoteWithAI({
        project_data: {
          description: messages.find(m => m.role === 'user')?.content || '',
          document_analyses: documentAnalyses
        },
        answers: conversationHistory.filter(m => m.role === 'user').map(m => ({
          question: m.content,
          answer: m.content
        })),
        conversation_history: conversationHistory,
        ...customerData
      });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie werden zur Detailansicht weitergeleitet.',
        type: 'text'
      }]);
      setConversationHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie werden zur Detailansicht weitergeleitet.',
        timestamp: new Date().toISOString()
      }]);
      setCurrentQuote(quoteData);
      setShowCustomerForm(false);
      
      // Navigate to quote detail view
      if (onNavigate && quoteData.quote && quoteData.quote.id) {
        onNavigate(`/quotes/${quoteData.quote.id}`);
      }
    } catch (err) {
      console.error('Failed to generate quote:', err);
      setError('Fehler beim Erstellen des Kostenvoranschlags: ' + (err.message || 'Unbekannter Fehler'));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, beim Erstellen des Kostenvoranschlags ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  // Authentifizierungsprüfung
  if (authLoading) {
    return <div>Lade Authentifizierung...</div>;
  }
  if (!isAuthenticated) {
    return <div>Bitte zuerst einloggen.</div>;
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto p-4">
      <div className="flex-1 flex flex-col">
        {/* Chat messages */}
        <ScrollArea ref={scrollRef} className="flex-1 p-4">
          <div className="space-y-4">
            {messages.map((message, index) => (
              <Card
                key={index}
                className={`p-4 ${
                  message.role === 'user' 
                    ? 'bg-blue-50 ml-auto' 
                    : 'bg-white'
                } max-w-[80%]`}
              >
                {message.type === 'file' ? (
                  <div className="flex items-center space-x-2">
                    <FileText className="h-4 w-4" />
                    <span>{message.content}</span>
                  </div>
                ) : (
                  <p className={message.type === 'error' ? 'text-red-500' : ''}>
                    {message.content}
                  </p>
                )}
              </Card>
            ))}
          </div>
        </ScrollArea>

        {/* Input area */}
        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="flex space-x-2">
            <Input
              value={inputValue}
              onChange={handleInputChange}
              placeholder="Beschreiben Sie Ihr Projekt..."
              disabled={loading}
              className="flex-1"
            />
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept="image/*, application/pdf"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
            >
              <Upload className="h-4 w-4" />
            </Button>
            <Button type="submit" disabled={loading || !inputValue.trim()}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
        </div>

        {/* Quote generation button */}
        {showQuoteButton && !currentQuote && !showCustomerForm && (
          <div className="p-4 border-t">
            <Button
              onClick={handleShowCustomerForm}
              disabled={loading}
              className="w-full"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Kostenvoranschlag erstellen
            </Button>
          </div>
        )}

        {/* Kundenformular */}
        {showCustomerForm && !currentQuote && (
          <div className="p-4 border-t bg-gray-50 rounded shadow mt-4">
            <form onSubmit={handleCustomerFormSubmit} className="space-y-4 max-w-lg mx-auto">
              <h2 className="text-lg font-semibold mb-2">Ihre Kontaktdaten für das Angebot</h2>
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <Input
                  name="customer_name"
                  value={customerData.customer_name}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Adresse *</label>
                <Input
                  name="customer_address"
                  value={customerData.customer_address}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">E-Mail *</label>
                <Input
                  name="customer_email"
                  type="email"
                  value={customerData.customer_email}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Telefon *</label>
                <Input
                  name="customer_phone"
                  type="tel"
                  value={customerData.customer_phone}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div className="flex space-x-2 mt-4">
                <Button type="submit" disabled={loading} className="w-full">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Angebot anfordern
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowCustomerForm(false)} disabled={loading}>
                  Abbrechen
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-4 text-red-500 text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatQuoteWizard; 