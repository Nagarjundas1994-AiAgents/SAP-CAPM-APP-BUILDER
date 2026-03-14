'use client';

import { useState } from 'react';
import { DollarSign, ChevronUp, ChevronDown, Zap, Brain } from 'lucide-react';

interface CostTrackerProps {
  sessionId: string;
  totalTokens: number;
  sonnetTokens: number;
  haikuTokens: number;
  estimatedCost: number;
  agentCosts?: Array<{
    agent_name: string;
    tokens: number;
    cost: number;
    model_tier: 'sonnet' | 'haiku';
  }>;
}

// Pricing per 1M tokens (example rates)
const PRICING = {
  sonnet: { input: 3.0, output: 15.0 }, // $3/$15 per 1M tokens
  haiku: { input: 0.25, output: 1.25 }, // $0.25/$1.25 per 1M tokens
};

export default function CostTracker({
  sessionId,
  totalTokens,
  sonnetTokens,
  haikuTokens,
  estimatedCost,
  agentCosts = [],
}: CostTrackerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatCost = (cost: number) => {
    return cost < 0.01 ? '<$0.01' : `$${cost.toFixed(2)}`;
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(2)}M`;
    } else if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-gray-900/95 backdrop-blur-sm border-t border-blue-500/20 shadow-2xl">
      {/* Main Bar */}
      <div className="max-w-7xl mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          {/* Left: Total Cost */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-green-500/20 border border-green-500/30 flex items-center justify-center">
                <DollarSign className="w-4 h-4 text-green-400" />
              </div>
              <div>
                <p className="text-xs text-gray-400">Estimated Cost</p>
                <p className="text-lg font-semibold text-green-400">{formatCost(estimatedCost)}</p>
              </div>
            </div>

            <div className="w-px h-8 bg-white/10" />

            {/* Total Tokens */}
            <div>
              <p className="text-xs text-gray-400">Total Tokens</p>
              <p className="text-sm font-medium text-white">{formatTokens(totalTokens)}</p>
            </div>
          </div>

          {/* Center: Model Breakdown */}
          <div className="flex items-center gap-6">
            {/* Sonnet */}
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              <div>
                <p className="text-xs text-gray-400">Sonnet (Strategic)</p>
                <p className="text-sm font-medium text-purple-400">{formatTokens(sonnetTokens)}</p>
              </div>
            </div>

            {/* Haiku */}
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-blue-400" />
              <div>
                <p className="text-xs text-gray-400">Haiku (Efficient)</p>
                <p className="text-sm font-medium text-blue-400">{formatTokens(haikuTokens)}</p>
              </div>
            </div>
          </div>

          {/* Right: Expand Button */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
          >
            <span className="text-xs text-gray-400">
              {isExpanded ? 'Hide' : 'Show'} Details
            </span>
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronUp className="w-4 h-4 text-gray-400" />
            )}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="border-t border-white/10 bg-black/40">
          <div className="max-w-7xl mx-auto px-6 py-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3">Per-Agent Cost Breakdown</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-64 overflow-y-auto">
              {agentCosts.map((agent) => (
                <div
                  key={agent.agent_name}
                  className="flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {agent.model_tier === 'sonnet' ? (
                      <Brain className="w-3 h-3 text-purple-400 flex-shrink-0" />
                    ) : (
                      <Zap className="w-3 h-3 text-blue-400 flex-shrink-0" />
                    )}
                    <span className="text-xs text-gray-300 truncate">
                      {agent.agent_name.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-500">{formatTokens(agent.tokens)}</span>
                    <span className="text-xs font-medium text-green-400 min-w-[3rem] text-right">
                      {formatCost(agent.cost)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Pricing Info */}
            <div className="mt-4 pt-4 border-t border-white/10">
              <p className="text-xs text-gray-500">
                Pricing: Sonnet ${PRICING.sonnet.input}/${PRICING.sonnet.output} per 1M tokens (input/output) • 
                Haiku ${PRICING.haiku.input}/${PRICING.haiku.output} per 1M tokens (input/output)
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
