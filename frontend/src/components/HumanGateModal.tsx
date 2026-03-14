'use client';

import { useState, useEffect } from 'react';
import { X, CheckCircle, AlertTriangle, RefreshCw } from 'lucide-react';

interface HumanGateModalProps {
  isOpen: boolean;
  onClose: () => void;
  gateData: {
    gate_id: string;
    gate_name: string;
    context?: any;
    session_id: string;
  } | null;
  onDecision: (decision: 'approve' | 'refine', refinementNotes?: string, targetAgent?: string) => Promise<void>;
}

const REFINEMENT_AGENTS = [
  { value: 'requirements', label: 'Requirements' },
  { value: 'enterprise_architecture', label: 'Enterprise Architecture' },
  { value: 'domain_modeling', label: 'Domain Modeling' },
  { value: 'data_modeling', label: 'Data Modeling' },
  { value: 'db_migration', label: 'DB Migration' },
  { value: 'integration', label: 'Integration' },
  { value: 'integration_design', label: 'Integration Design' },
  { value: 'service_exposure', label: 'Service Exposure' },
  { value: 'error_handling', label: 'Error Handling' },
  { value: 'audit_logging', label: 'Audit Logging' },
  { value: 'api_governance', label: 'API Governance' },
  { value: 'business_logic', label: 'Business Logic' },
  { value: 'ux_design', label: 'UX Design' },
  { value: 'fiori_ui', label: 'Fiori UI' },
  { value: 'security', label: 'Security' },
  { value: 'multitenancy', label: 'Multitenancy' },
  { value: 'i18n', label: 'I18n' },
  { value: 'feature_flags', label: 'Feature Flags' },
  { value: 'compliance_check', label: 'Compliance Check' },
  { value: 'extension', label: 'Extension' },
  { value: 'performance_review', label: 'Performance Review' },
  { value: 'ci_cd', label: 'CI/CD' },
  { value: 'deployment', label: 'Deployment' },
  { value: 'testing', label: 'Testing' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'observability', label: 'Observability' },
  { value: 'project_assembly', label: 'Project Assembly' },
  { value: 'project_verification', label: 'Project Verification' },
  { value: 'validation', label: 'Validation' },
];

export default function HumanGateModal({
  isOpen,
  onClose,
  gateData,
  onDecision,
}: HumanGateModalProps) {
  const [showRefinement, setShowRefinement] = useState(false);
  const [refinementNotes, setRefinementNotes] = useState('');
  const [targetAgent, setTargetAgent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setShowRefinement(false);
      setRefinementNotes('');
      setTargetAgent('');
    }
  }, [isOpen]);

  if (!isOpen || !gateData) return null;

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await onDecision('approve');
      onClose();
    } catch (error) {
      console.error('Failed to approve:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRefine = async () => {
    if (!refinementNotes.trim() || !targetAgent) {
      alert('Please provide refinement notes and select a target agent');
      return;
    }

    setIsSubmitting(true);
    try {
      await onDecision('refine', refinementNotes, targetAgent);
      onClose();
    } catch (error) {
      console.error('Failed to request refinement:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-blue-500/30 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">
                {gateData.gate_name}
              </h2>
              <p className="text-sm text-gray-400">{gateData.gate_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
            disabled={isSubmitting}
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Agent Output Summary */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-gray-300">Review Context</h3>
            <div className="bg-black/40 border border-white/10 rounded-lg p-4 font-mono text-sm text-gray-300 max-h-64 overflow-y-auto">
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(gateData.context || {}, null, 2)}
              </pre>
            </div>
          </div>

          {/* Decision Section */}
          {!showRefinement ? (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-300">Review & Decision</h3>
              <p className="text-sm text-gray-400">
                Please review the agent output above. You can approve to continue or request refinement.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-gray-300">Request Refinement</h3>
              
              {/* Refinement Notes */}
              <div className="space-y-2">
                <label className="text-sm text-gray-400">
                  Refinement Notes <span className="text-red-400">*</span>
                </label>
                <textarea
                  value={refinementNotes}
                  onChange={(e) => setRefinementNotes(e.target.value)}
                  placeholder="Describe what needs to be refined..."
                  className="w-full h-32 bg-black/40 border border-white/10 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 resize-none"
                />
              </div>

              {/* Target Agent Selector */}
              <div className="space-y-2">
                <label className="text-sm text-gray-400">
                  Target Agent <span className="text-red-400">*</span>
                </label>
                <select
                  value={targetAgent}
                  onChange={(e) => setTargetAgent(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-blue-500/50"
                >
                  <option value="">Select agent to refine...</option>
                  {REFINEMENT_AGENTS.map((agent) => (
                    <option key={agent.value} value={agent.value}>
                      {agent.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-white/10">
          {!showRefinement ? (
            <>
              <button
                onClick={() => setShowRefinement(true)}
                disabled={isSubmitting}
                className="px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                <RefreshCw className="w-4 h-4" />
                Request Refinement
              </button>
              <button
                onClick={handleApprove}
                disabled={isSubmitting}
                className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                    Approving...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Approve & Continue
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setShowRefinement(false)}
                disabled={isSubmitting}
                className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRefine}
                disabled={isSubmitting || !refinementNotes.trim() || !targetAgent}
                className="px-4 py-2 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Submit Refinement
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
