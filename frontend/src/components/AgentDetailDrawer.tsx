'use client';

import { X, Brain, Zap, RefreshCw, FileText, CheckCircle, AlertCircle, Clock, DollarSign } from 'lucide-react';
import { AgentExecution } from '@/lib/api';

interface AgentDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  agent: {
    name: string;
    displayName: string;
    description: string;
  } | null;
  execution: AgentExecution | null;
  modelTier?: 'sonnet' | 'haiku';
  ragDocs?: string[];
  validationRules?: Array<{
    rule: string;
    passed: boolean;
  }>;
  tokenUsage?: {
    input: number;
    output: number;
    total: number;
    cost: number;
  };
}

export default function AgentDetailDrawer({
  isOpen,
  onClose,
  agent,
  execution,
  modelTier = 'haiku',
  ragDocs = [],
  validationRules = [],
  tokenUsage,
}: AgentDetailDrawerProps) {
  if (!isOpen || !agent) return null;

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-2xl bg-gray-900 border-l border-blue-500/20 shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              modelTier === 'sonnet'
                ? 'bg-purple-500/20 border border-purple-500/30'
                : 'bg-blue-500/20 border border-blue-500/30'
            }`}>
              {modelTier === 'sonnet' ? (
                <Brain className="w-5 h-5 text-purple-400" />
              ) : (
                <Zap className="w-5 h-5 text-blue-400" />
              )}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">{agent.displayName}</h2>
              <p className="text-sm text-gray-400">{agent.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Model Tier Badge */}
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              modelTier === 'sonnet'
                ? 'bg-purple-500/10 border border-purple-500/30 text-purple-400'
                : 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
            }`}>
              {modelTier === 'sonnet' ? '🧠 Sonnet (Strategic)' : '⚡ Haiku (Efficient)'}
            </span>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-gray-300">Description</h3>
            <p className="text-sm text-gray-400">{agent.description}</p>
          </div>

          {/* Execution Status */}
          {execution && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-300">Execution Status</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Status</p>
                  <div className="flex items-center gap-2">
                    {execution.status === 'completed' ? (
                      <CheckCircle className="w-4 h-4 text-green-400" />
                    ) : execution.status === 'failed' ? (
                      <AlertCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <Clock className="w-4 h-4 text-blue-400" />
                    )}
                    <span className="text-sm font-medium text-white capitalize">{execution.status}</span>
                  </div>
                </div>

                {execution.duration_ms && (
                  <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                    <p className="text-xs text-gray-400 mb-1">Duration</p>
                    <p className="text-sm font-medium text-white">
                      {(execution.duration_ms / 1000).toFixed(2)}s
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Retry History */}
          {execution && execution.retry_count > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Retry History
              </h3>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
                <p className="text-sm text-amber-400">
                  Auto-corrected {execution.retry_count} {execution.retry_count === 1 ? 'time' : 'times'}
                </p>
              </div>
            </div>
          )}

          {/* Token Usage & Cost */}
          {tokenUsage && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Token Usage & Cost
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Input</p>
                  <p className="text-sm font-medium text-white">{formatTokens(tokenUsage.input)}</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Output</p>
                  <p className="text-sm font-medium text-white">{formatTokens(tokenUsage.output)}</p>
                </div>
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Cost</p>
                  <p className="text-sm font-medium text-green-400">
                    ${tokenUsage.cost.toFixed(4)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* RAG Documents Used */}
          {ragDocs.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                RAG Documents Used ({ragDocs.length})
              </h3>
              <div className="space-y-2">
                {ragDocs.map((doc, idx) => (
                  <div
                    key={idx}
                    className="bg-white/5 border border-white/10 rounded-lg p-3 text-xs text-gray-400 font-mono"
                  >
                    {doc}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Validation Rules */}
          {validationRules.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-300">Validation Rules</h3>
              <div className="space-y-2">
                {validationRules.map((rule, idx) => (
                  <div
                    key={idx}
                    className={`flex items-start gap-2 p-3 rounded-lg border ${
                      rule.passed
                        ? 'bg-green-500/5 border-green-500/20'
                        : 'bg-red-500/5 border-red-500/20'
                    }`}
                  >
                    {rule.passed ? (
                      <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    )}
                    <span className={`text-sm ${rule.passed ? 'text-green-400' : 'text-red-400'}`}>
                      {rule.rule}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Details */}
          {execution?.error && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400" />
                Error Details
              </h3>
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                <p className="text-sm text-red-400 font-mono">{execution.error}</p>
              </div>
            </div>
          )}

          {/* Raw Output Preview */}
          {execution && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-300">Raw Output Preview</h3>
              <div className="bg-black/40 border border-white/10 rounded-lg p-4 font-mono text-xs text-gray-300 max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap">
                  {JSON.stringify(execution, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
