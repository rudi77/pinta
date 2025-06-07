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
      // Add file message to chat
      setMessages(prev => [...prev, {
        role: 'user',
        content: `Datei hochgeladen: ${file.name}`,
        type: 'file',
        filename: file.name
      }]);

      // Upload file
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await apiClient.uploadDocument(formData);
      
      // Add AI response to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
        type: 'text'
      }]);

      // Update conversation history
      setConversationHistory(prev => [...prev, {
        role: 'user',
        content: `Datei hochgeladen: ${file.name}`,
        timestamp: new Date().toISOString()
      }, {
        role: 'assistant',
        content: 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
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

  const handleGenerateQuote = async () => {
    setLoading(true);
    setError(null);

    try {
      // Generate quote
      const quoteData = await apiClient.generateQuoteWithAI({
        project_data: {
          description: messages.find(m => m.role === 'user')?.content || ''
        },
        answers: conversationHistory.filter(m => m.role === 'user').map(m => ({
          question: m.content,
          answer: m.content
        })),
        conversation_history: conversationHistory
      });

      // Add success message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie können ihn jetzt speichern und als PDF herunterladen.',
        type: 'text'
      }]);

      // Update conversation history
      setConversationHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie können ihn jetzt speichern und als PDF herunterladen.',
        timestamp: new Date().toISOString()
      }]);

      // Set current quote
      setCurrentQuote(quoteData);

    } catch (err) {
      console.error('Failed to generate quote:', err);
      setError('Fehler beim Erstellen des Kostenvoranschlags: ' + (err.message || 'Unbekannter Fehler'));
      
      // Add error message to chat
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
        {showQuoteButton && !currentQuote && (
          <div className="p-4 border-t">
            <Button
              onClick={handleGenerateQuote}
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