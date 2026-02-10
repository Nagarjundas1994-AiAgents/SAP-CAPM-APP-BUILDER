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
  logs?: Record<string, string>;
}

export default function AgentProgress({
  agents,
  executions,
  currentAgent,
  logs = {},
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
    <div className="space-y-4">
      {agents.map((agent, index) => {
        const status = getAgentStatus(agent.name);
        const execution = executions.find((e) => e.agent_name === agent.name);
        const agentLogs = logs[agent.name];

        return (
          <div key={agent.name} className="flex flex-col gap-2">
            <div
              className={`flex items-start gap-4 p-4 rounded-xl transition-all relative overflow-hidden ${
                status === 'running'
                  ? 'bg-blue-500/10 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.1)]'
                  : status === 'completed'
                  ? 'bg-green-500/5 border border-green-500/20'
                  : status === 'failed'
                  ? 'bg-red-500/10 border border-red-500/30'
                  : 'bg-white/5 border border-white/10 opacity-50'
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
                  <span className="text-xs text-blue-400 font-mono">[{index + 1}/{agents.length}]</span>
                  <span className="text-xs text-gray-500">Agent {agent.name.replace('_', ' ').toUpperCase()}</span>
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
                  <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-700" />
                    Completed in {(execution.duration_ms / 1000).toFixed(2)}s
                  </p>
                )}

                {/* Error */}
                {execution?.error && (
                  <p className="text-xs text-red-400 mt-1 bg-red-400/10 p-2 rounded-lg border border-red-400/20">
                    {execution.error}
                  </p>
                )}
              </div>

              {/* Progress bar for running agent */}
              {status === 'running' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 overflow-hidden">
                  <div className="agent-progress-bar h-full bg-blue-500 shadow-[0_0_10px_#3b82f6]" />
                </div>
              )}
            </div>

            {/* Real-time Logs */}
            {(status === 'running' || agentLogs) && (
              <div className="ml-12 mr-2">
                <div className="bg-black/40 border border-white/5 rounded-lg p-3 font-mono text-[11px] max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10">
                  {agentLogs ? (
                    <div className="space-y-1">
                      {agentLogs.split('\n').filter(Boolean).map((log, i) => (
                        <div key={i} className="flex gap-2 text-gray-400">
                          <span className="text-blue-500/50 flex-shrink-0 animate-pulse">›</span>
                          <span className="break-all">{log}</span>
                        </div>
                      ))}
                      {status === 'running' && (
                        <div className="flex gap-2 text-blue-400 animate-pulse">
                          <span>›</span>
                          <span className="animate-blink italic">Agent is thinking...</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-gray-600 italic">Initializing agent...</div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
