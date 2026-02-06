'use client';

import { Check, Loader2, AlertCircle, Circle } from 'lucide-react';
import { AgentExecution } from '@/lib/api';

interface AgentProgressProps {
  agents: {
    name: string;
    displayName: string;
    description: string;
  }[];
  executions: AgentExecution[];
  currentAgent: string | null;
}

export default function AgentProgress({
  agents,
  executions,
  currentAgent,
}: AgentProgressProps) {
  const getAgentStatus = (agentName: string) => {
    const execution = executions.find((e) => e.agent_name === agentName);
    if (execution) {
      return execution.status;
    }
    if (currentAgent === agentName) {
      return 'running';
    }
    return 'pending';
  };

  return (
    <div className="space-y-3">
      {agents.map((agent, index) => {
        const status = getAgentStatus(agent.name);
        const execution = executions.find((e) => e.agent_name === agent.name);

        return (
          <div
            key={agent.name}
            className={`flex items-start gap-4 p-4 rounded-xl transition-all ${
              status === 'running'
                ? 'bg-blue-500/10 border border-blue-500/30'
                : status === 'completed'
                ? 'bg-green-500/5 border border-green-500/20'
                : status === 'failed'
                ? 'bg-red-500/10 border border-red-500/30'
                : 'bg-white/5 border border-white/10'
            }`}
          >
            {/* Status icon */}
            <div className="flex-shrink-0 mt-0.5">
              {status === 'completed' ? (
                <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
                  <Check className="w-4 h-4 text-white" />
                </div>
              ) : status === 'running' ? (
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                </div>
              ) : status === 'failed' ? (
                <div className="w-8 h-8 rounded-full bg-red-500 flex items-center justify-center">
                  <AlertCircle className="w-4 h-4 text-white" />
                </div>
              ) : (
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
                  <Circle className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </div>

            {/* Agent info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Agent {index + 1}</span>
              </div>
              <h3 className={`font-medium ${
                status === 'pending' ? 'text-gray-500' : 'text-white'
              }`}>
                {agent.displayName}
              </h3>
              <p className="text-sm text-gray-400 mt-0.5">
                {agent.description}
              </p>

              {/* Duration */}
              {execution?.duration_ms && (
                <p className="text-xs text-gray-500 mt-1">
                  Completed in {(execution.duration_ms / 1000).toFixed(2)}s
                </p>
              )}

              {/* Error */}
              {execution?.error && (
                <p className="text-xs text-red-400 mt-1">
                  {execution.error}
                </p>
              )}
            </div>

            {/* Progress bar for running agent */}
            {status === 'running' && (
              <div className="absolute bottom-0 left-0 right-0 h-1 overflow-hidden rounded-b-xl">
                <div className="agent-progress-bar h-full" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
