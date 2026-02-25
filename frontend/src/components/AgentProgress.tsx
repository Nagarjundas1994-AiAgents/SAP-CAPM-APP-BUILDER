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

                {/* Duration & Retries */}
                <div className="flex items-center gap-3 mt-1">
                  {execution?.duration_ms && (
                    <p className="text-xs text-gray-500 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-700" />
                      Completed in {(execution.duration_ms / 1000).toFixed(2)}s
                    </p>
                  )}
                  {execution?.retry_count && execution.retry_count > 0 && (
                    <p className="text-xs text-amber-400 flex items-center gap-1 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20">
                      <AlertCircle className="w-3 h-3" />
                      Auto-corrected ({execution.retry_count} {execution.retry_count === 1 ? 'retry' : 'retries'})
                    </p>
                  )}
                </div>

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

            {/* Real-time Logs (Hacker Terminal Style) */}
            {(status === 'running' || agentLogs) && (
              <div className="ml-12 mr-2 mt-2">
                <div className="bg-black/80 border border-blue-500/20 rounded-lg p-4 font-mono text-[13px] max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-blue-500/20 shadow-inner relative group">
                  <div className="absolute top-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/50"></div>
                  </div>
                  
                  {agentLogs ? (
                    <div className="space-y-1.5">
                      {agentLogs.split('\n').filter(Boolean).map((log, i) => {
                        const isError = log.toLowerCase().includes('error') || log.toLowerCase().includes('failed');
                        const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('completed');
                        
                        return (
                          <div key={i} className="flex gap-3 text-gray-300">
                            <span className="text-blue-500/50 flex-shrink-0 select-none">~</span>
                            <span className={`break-all tracking-wide ${isError ? 'text-red-400' : isSuccess ? 'text-green-400' : 'text-blue-100/80'}`}>
                              {log}
                            </span>
                          </div>
                        );
                      })}
                      {status === 'running' && (
                        <div className="flex gap-3 text-blue-400 pt-2">
                          <span className="select-none animate-pulse">~</span>
                          <span className="animate-pulse flex items-center gap-1">
                            Processing
                            <span className="flex gap-1 items-center h-full">
                              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"></span>
                            </span>
                          </span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-gray-500 italic">
                      <span className="animate-spin w-3 h-3 border-2 border-gray-500 border-t-transparent rounded-full" />
                      Initializing terminal stream...
                    </div>
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
