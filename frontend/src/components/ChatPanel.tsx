'use client';

import { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  Loader2,
  MessageSquare,
  Zap,
  RefreshCw,
} from 'lucide-react';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  message: string;
  entities_preview?: any[];
  suggested_followups?: string[];
  timestamp: string;
}

interface ChatPanelProps {
  sessionId: string;
  messages: ChatMessage[];
  onSendMessage: (message: string) => Promise<void>;
  onRegenerate: () => void;
  isProcessing: boolean;
  isRegenerating: boolean;
}

export default function ChatPanel({
  sessionId,
  messages,
  onSendMessage,
  onRegenerate,
  isProcessing,
  isRegenerating,
}: ChatPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, [isProcessing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isProcessing) return;
    const msg = inputValue.trim();
    setInputValue('');
    await onSendMessage(msg);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (isProcessing) return;
    onSendMessage(suggestion);
  };

  const EXAMPLE_PROMPTS = [
    'Add a search field to the Employee entity',
    'Add a Payroll entity with salary and month',
    'Change theme to sap_fiori_3_dark',
    'Add an approval workflow for leave requests',
    'Remove the description field from Department',
  ];

  return (
    <div className="flex flex-col h-full bg-gray-950/50 rounded-xl border border-white/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-purple-500/10">
        <div className="p-2 bg-blue-500/20 rounded-lg">
          <MessageSquare className="w-5 h-5 text-blue-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">Modify Your App</h3>
          <p className="text-xs text-gray-400">Describe changes in natural language</p>
        </div>
        <button
          onClick={onRegenerate}
          disabled={isRegenerating || isProcessing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-green-500/20"
        >
          {isRegenerating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          {isRegenerating ? 'Regenerating...' : 'Regenerate'}
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth">
        {messages.length === 0 ? (
          /* Welcome state */
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="p-4 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-2xl mb-4">
              <Sparkles className="w-10 h-10 text-blue-400" />
            </div>
            <h4 className="text-lg font-semibold text-white mb-2">
              Refine Your Application
            </h4>
            <p className="text-sm text-gray-400 mb-6 max-w-sm">
              Your app is built! Now you can modify it using natural language. Try one of these:
            </p>
            <div className="space-y-2 w-full max-w-md">
              {EXAMPLE_PROMPTS.slice(0, 3).map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(prompt)}
                  className="w-full text-left px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/30 rounded-xl text-sm text-gray-300 hover:text-white transition-all group"
                >
                  <Zap className="w-3.5 h-3.5 text-blue-400 inline mr-2 group-hover:text-blue-300" />
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message list */
          <>
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex gap-3 ${
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                } animate-in fade-in slide-in-from-bottom-2 duration-300`}
              >
                {msg.role !== 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/30 to-purple-500/30 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-blue-400" />
                  </div>
                )}

                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-md'
                      : 'bg-white/5 border border-white/10 text-gray-200 rounded-tl-md'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.message}</p>

                  {/* Entity count badge */}
                  {msg.entities_preview && msg.entities_preview.length > 0 && (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">
                        {msg.entities_preview.length} entities
                      </span>
                    </div>
                  )}

                  {/* Follow-up suggestions */}
                  {msg.suggested_followups && msg.suggested_followups.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {msg.suggested_followups.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => handleSuggestionClick(suggestion)}
                          disabled={isProcessing}
                          className="text-xs px-2.5 py-1 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 hover:text-blue-200 rounded-full border border-blue-500/20 transition-all disabled:opacity-50"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-500/30 flex items-center justify-center">
                    <User className="w-4 h-4 text-blue-300" />
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {isProcessing && (
              <div className="flex gap-3 justify-start animate-in fade-in duration-300">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/30 to-purple-500/30 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-md px-4 py-3">
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                    <span>Analyzing your request...</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="px-4 pb-4 pt-2 border-t border-white/10">
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe how you'd like to modify your app..."
            rows={1}
            disabled={isProcessing}
            className="w-full pl-4 pr-12 py-3 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 disabled:opacity-50 transition-all"
            style={{ minHeight: '44px', maxHeight: '120px' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = '44px';
              target.style.height = Math.min(target.scrollHeight, 120) + 'px';
            }}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isProcessing}
            className="absolute right-2 bottom-2 p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-[10px] text-gray-600 mt-1.5 text-center">
          Press Enter to send • Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
