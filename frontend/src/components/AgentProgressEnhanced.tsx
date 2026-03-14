'use client';

import { Check, Loader2, AlertCircle, Circle, GitMerge } from 'lucide-react';
import { AgentExecution } from '@/lib/api';

interface AgentProgressEnhancedProps {
  agents: {
    name: string;
    displayName: string;
    description: string;
  }[];
  executions: AgentExecution[];
  currentAgent: string | null;
  logs?: Record<string, string>;
}

// Parallel phase definitions
const PARALLEL_PHASES = {
  phase1: ['service_exposure', 'integration_design'],
  phase2: ['error_handling', 'audit_logging', 'api_governance'],
  phase3: ['fiori_ui', 'security', 'multitenancy', 'i18n', 'feature_flags'],
  phase4: ['testing', 'documentation', 'observability'],
};

export default function AgentProgressEnhanced({
  agents,
  executions,
  currentAgent,
  logs = {},
}: AgentProgressEnhancedProps) {
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

  const isInParallelPhase = (agentName: string): string | null => {
    for (const [phase, agentNames] of Object.entries(PARALLEL_PHASES)) {
      if (agentNames.includes(agentName)) {
        return phase;
      }
    }
    return null;
  };

  // Group agents by parallel phases
  const groupedAgents: Array<{ type: 'single' | 'parallel'; agents: typeof agents; phase?: string }> = [];
  let i = 0;
  
  while (i < agents.length) {
    const agent = agents[i];
    const phase = isInParallelPhase(agent.name);
    
    if (phase) {
      // Find all agents in this parallel phase
      const phaseAgents = agents.filter(a => isInParallelPhase(a.name) === phase);
      groupedAgents.push({ type: 'parallel', agents: phaseAgents, phase });
      // Skip all agents in this phase
      i += phaseAgents.length;
    } else {
      groupedAgents.push({ type: 'single', agents: [agent] });
      i++;
    }
  }

  const renderAgent = (agent: typeof agents[0], index: number, isParallel: boolean = false) => {
    const status = getAgentStatus(agent.name);
    const execution = executions.find((e) => e.agent_name === agent.name);
    const agentLogs = logs[agent.name];
    
    // Check if this agent is being retried due to self-healing
    const isRetrying = status === 'running' && execution && execution.status === 'completed';
    const isSelfHealing = agentLogs?.includes('Self-healing') || agentLogs?.includes('self-healing') || agentLogs?.includes('correction');

    return (
      <div key={agent.name} className={`flex flex-col gap-2 ${isParallel ? 'flex-1 min-w-0' : ''}`}>
        <div
          className={`flex items-start gap-4 p-4 rounded-xl transition-all relative overflow-hidden ${
            isRetrying || isSelfHealing
              ? 'bg-amber-500/10 border border-amber-500/40 shadow-[0_0_20px_rgba(251,191,36,0.2)] animate-pulse'
              : status === 'running'
              ? 'bg-blue-500/10 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.1)]'
              : status === 'completed'
              ? 'bg-green-500/5 border border-green-500/20'
              : status === 'failed'
              ? 'bg-red-500/10 border border-red-500/30'
              : 'bg-white/5 border border-white/10 opacity-50'
          }`}
        >
          {/* Self-healing badge */}
          {(isRetrying || isSelfHealing) && (
            <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-amber-500/20 px-2 py-1 rounded-full border border-amber-500/40 animate-pulse">
              <div className="w-2 h-2 rounded-full bg-amber-500 animate-ping absolute" />
              <div className="w-2 h-2 rounded-full bg-amber-500 relative" />
              <span className="text-xs font-medium text-amber-300">Self-Healing</span>
            </div>
          )}
          {/* Status icon */}
          <div className="flex-shrink-0 mt-0.5">
            {isRetrying || isSelfHealing ? (
              <div className="w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center animate-pulse">
                <AlertCircle className="w-4 h-4 text-white animate-spin" />
              </div>
            ) : status === 'completed' ? (
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
              {!isParallel && (
                <span className="text-xs text-blue-400 font-mono">[{index + 1}/{agents.length}]</span>
              )}
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
                  {(execution.duration_ms / 1000).toFixed(2)}s
                </p>
              )}
              {execution?.retry_count && execution.retry_count > 0 && (
                <p className="text-xs text-amber-400 flex items-center gap-1 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20">
                  <AlertCircle className="w-3 h-3" />
                  {execution.retry_count} {execution.retry_count === 1 ? 'retry' : 'retries'}
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
          {(status === 'running' || isRetrying || isSelfHealing) && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 overflow-hidden">
              <div className={`agent-progress-bar h-full ${
                isRetrying || isSelfHealing 
                  ? 'bg-amber-500 shadow-[0_0_10px_#f59e0b]' 
                  : 'bg-blue-500 shadow-[0_0_10px_#3b82f6]'
              }`} />
            </div>
          )}
        </div>

        {/* Real-time Logs (Hacker Terminal Style) */}
        {(status === 'running' || agentLogs || isRetrying || isSelfHealing) && !isParallel && (
          <div className="ml-12 mr-2 mt-2">
            <div className={`bg-black/80 border rounded-lg p-4 font-mono text-[13px] max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-blue-500/20 shadow-inner relative group ${
              isRetrying || isSelfHealing 
                ? 'border-amber-500/40 shadow-[0_0_15px_rgba(251,191,36,0.1)]' 
                : 'border-blue-500/20'
            }`}>
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
                    const isHealing = log.toLowerCase().includes('self-healing') || log.toLowerCase().includes('correction') || log.toLowerCase().includes('routing back');
                    
                    return (
                      <div key={i} className="flex gap-3 text-gray-300">
                        <span className={`flex-shrink-0 select-none ${
                          isHealing ? 'text-amber-500/70 animate-pulse' : 'text-blue-500/50'
                        }`}>~</span>
                        <span className={`break-all tracking-wide ${
                          isHealing ? 'text-amber-300 font-semibold animate-pulse' :
                          isError ? 'text-red-400' : 
                          isSuccess ? 'text-green-400' : 
                          'text-blue-100/80'
                        }`}>
                          {log}
                        </span>
                      </div>
                    );
                  })}
                  {(status === 'running' || isRetrying || isSelfHealing) && (
                    <div className={`flex gap-3 pt-2 ${
                      isRetrying || isSelfHealing ? 'text-amber-400' : 'text-blue-400'
                    }`}>
                      <span className="select-none animate-pulse">~</span>
                      <span className="animate-pulse flex items-center gap-1">
                        {isRetrying || isSelfHealing ? 'Retrying with corrections' : 'Processing'}
                        <span className="flex gap-1 items-center h-full">
                          <span className={`w-1 h-1 rounded-full animate-bounce [animation-delay:-0.3s] ${
                            isRetrying || isSelfHealing ? 'bg-amber-400' : 'bg-blue-400'
                          }`}></span>
                          <span className={`w-1 h-1 rounded-full animate-bounce [animation-delay:-0.15s] ${
                            isRetrying || isSelfHealing ? 'bg-amber-400' : 'bg-blue-400'
                          }`}></span>
                          <span className={`w-1 h-1 rounded-full animate-bounce ${
                            isRetrying || isSelfHealing ? 'bg-amber-400' : 'bg-blue-400'
                          }`}></span>
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
  };

  return (
    <div className="space-y-4">
      {groupedAgents.map((group, groupIndex) => {
        if (group.type === 'single') {
          return renderAgent(group.agents[0], groupIndex, false);
        } else {
          // Parallel phase
          const phaseStatus = group.agents.every(a => getAgentStatus(a.name) === 'completed')
            ? 'completed'
            : group.agents.some(a => getAgentStatus(a.name) === 'running')
            ? 'running'
            : group.agents.some(a => getAgentStatus(a.name) === 'failed')
            ? 'failed'
            : 'pending';

          return (
            <div key={group.phase} className="space-y-3">
              {/* Parallel phase header */}
              <div className="flex items-center gap-3 px-2">
                <GitMerge className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-purple-400">
                  Parallel Phase {group.phase?.replace('phase', '')} - {group.agents.length} agents
                </span>
                <div className="flex-1 h-px bg-purple-400/20" />
                {phaseStatus === 'completed' && (
                  <span className="text-xs text-green-400 flex items-center gap-1">
                    <Check className="w-3 h-3" />
                    All complete
                  </span>
                )}
                {phaseStatus === 'running' && (
                  <span className="text-xs text-blue-400 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    In progress
                  </span>
                )}
              </div>

              {/* Parallel agents in horizontal layout */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {group.agents.map((agent) => renderAgent(agent, groupIndex, true))}
              </div>

              {/* Fan-in connector */}
              <div className="flex items-center justify-center py-2">
                <div className="flex flex-col items-center gap-1">
                  <div className="w-px h-4 bg-purple-400/30" />
                  <div className="w-3 h-3 rounded-full border-2 border-purple-400/50 bg-purple-400/10" />
                  <div className="w-px h-4 bg-purple-400/30" />
                </div>
              </div>
            </div>
          );
        }
      })}
    </div>
  );
}
