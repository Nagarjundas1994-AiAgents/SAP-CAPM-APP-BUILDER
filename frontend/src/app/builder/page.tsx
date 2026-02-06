'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import WizardLayout from '@/components/WizardLayout';
import AgentProgress from '@/components/AgentProgress';
import {
  createSession,
  updateSession,
  startGeneration,
  getArtifacts,
  getDownloadUrl,
  Session,
  GenerationResult,
  AgentExecution,
} from '@/lib/api';
import {
  Briefcase,
  Database,
  Server,
  Code2,
  Palette,
  Shield,
  Puzzle,
  Rocket,
  Download,
  FileCode,
  FolderTree,
  CheckCircle2,
} from 'lucide-react';

// Wizard steps
const STEPS = [
  { id: 0, name: 'Project Setup', shortName: 'Project' },
  { id: 1, name: 'Business Domain', shortName: 'Domain' },
  { id: 2, name: 'Data Model', shortName: 'Data' },
  { id: 3, name: 'Services & APIs', shortName: 'Services' },
  { id: 4, name: 'Fiori UI', shortName: 'UI' },
  { id: 5, name: 'Security', shortName: 'Security' },
  { id: 6, name: 'Review & Generate', shortName: 'Generate' },
  { id: 7, name: 'Download', shortName: 'Download' },
];

// Agent definitions
const AGENTS = [
  { name: 'requirements', displayName: 'Requirements Agent', description: 'Analyzing business requirements' },
  { name: 'data_modeling', displayName: 'Data Modeling Agent', description: 'Generating CDS schemas' },
  { name: 'service_exposure', displayName: 'Service Agent', description: 'Creating OData services' },
  { name: 'business_logic', displayName: 'Business Logic Agent', description: 'Writing event handlers' },
  { name: 'fiori_ui', displayName: 'Fiori UI Agent', description: 'Building Fiori Elements app' },
  { name: 'security', displayName: 'Security Agent', description: 'Configuring authorization' },
  { name: 'extension', displayName: 'Extension Agent', description: 'Adding extension points' },
  { name: 'deployment', displayName: 'Deployment Agent', description: 'Creating deployment config' },
  { name: 'validation', displayName: 'Validation Agent', description: 'Validating SAP compliance' },
];

// Domain templates
const DOMAIN_TEMPLATES = [
  { id: 'sales', name: 'Sales & Distribution', icon: Briefcase, entities: ['Customer', 'SalesOrder', 'Product'] },
  { id: 'inventory', name: 'Inventory Management', icon: Database, entities: ['Material', 'Stock', 'Warehouse'] },
  { id: 'hr', name: 'Human Resources', icon: Briefcase, entities: ['Employee', 'Department', 'Leave'] },
  { id: 'custom', name: 'Custom Domain', icon: Puzzle, entities: [] },
];

export default function BuilderPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [agentHistory, setAgentHistory] = useState<AgentExecution[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);

  // Form state
  const [projectName, setProjectName] = useState('');
  const [projectNamespace, setProjectNamespace] = useState('com.company');
  const [projectDescription, setProjectDescription] = useState('');
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [entities, setEntities] = useState<string[]>([]);
  const [newEntity, setNewEntity] = useState('');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [fioriTheme, setFioriTheme] = useState('sap_horizon');
  const [authType, setAuthType] = useState('mock');

  // Validation
  const canProceed = () => {
    switch (currentStep) {
      case 0:
        return projectName.trim().length >= 3;
      case 1:
        return selectedDomain !== null;
      case 2:
        return entities.length > 0;
      case 3:
      case 4:
      case 5:
        return true;
      case 6:
        return !isGenerating;
      case 7:
        return result !== null;
      default:
        return true;
    }
  };

  // Handle domain selection
  const handleDomainSelect = (domainId: string) => {
    setSelectedDomain(domainId);
    const template = DOMAIN_TEMPLATES.find((d) => d.id === domainId);
    if (template && template.entities.length > 0) {
      setEntities(template.entities);
    }
  };

  // Add entity
  const handleAddEntity = () => {
    if (newEntity.trim() && !entities.includes(newEntity.trim())) {
      setEntities([...entities, newEntity.trim()]);
      setNewEntity('');
    }
  };

  // Remove entity
  const handleRemoveEntity = (entity: string) => {
    setEntities(entities.filter((e) => e !== entity));
  };

  // Handle next step
  const handleNext = async () => {
    if (currentStep === 0 && !session) {
      // Create session
      try {
        const newSession = await createSession({
          project_name: projectName,
          project_namespace: projectNamespace,
          project_description: projectDescription,
        });
        setSession(newSession);
      } catch (error) {
        console.error('Failed to create session:', error);
        return;
      }
    }

    if (currentStep === 6) {
      // Start generation
      await handleGenerate();
    } else if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  // Handle previous step
  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Handle generation
  const handleGenerate = async () => {
    if (!session) return;

    setIsGenerating(true);
    setAgentHistory([]);
    setCurrentAgent('requirements');

    try {
      // Update session with all configuration
      await updateSession(session.id, {
        configuration: {
          domain: selectedDomain,
          entities: entities.map((name) => ({ name, fields: [] })),
          llm_provider: llmProvider,
          fiori_theme: fioriTheme,
          auth_type: authType,
          fiori_main_entity: entities[0] || 'Entity',
        },
      });

      // Start generation
      const status = await startGeneration(session.id, {
        llm_provider: llmProvider,
      });

      setAgentHistory(status.agent_history);
      setCurrentAgent(null);

      // Get artifacts
      const artifacts = await getArtifacts(session.id);
      setResult(artifacts);

      setCurrentStep(7); // Go to download step
    } catch (error) {
      console.error('Generation failed:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Count total files
  const getTotalFiles = () => {
    if (!result) return 0;
    return (
      result.artifacts_db.length +
      result.artifacts_srv.length +
      result.artifacts_app.length +
      result.artifacts_deployment.length +
      result.artifacts_docs.length
    );
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      // Step 0: Project Setup
      case 0:
        return (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Project Name *
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="My SAP App"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Namespace
              </label>
              <input
                type="text"
                value={projectNamespace}
                onChange={(e) => setProjectNamespace(e.target.value)}
                placeholder="com.company.app"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Description
              </label>
              <textarea
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
                placeholder="Brief description of your application..."
                rows={3}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                LLM Provider
              </label>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="openai">OpenAI GPT-4</option>
                <option value="gemini">Google Gemini</option>
                <option value="deepseek">DeepSeek</option>
                <option value="kimi">Kimi K2.5</option>
              </select>
            </div>
          </div>
        );

      // Step 1: Business Domain
      case 1:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Select a domain template or choose Custom to define your own entities.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              {DOMAIN_TEMPLATES.map((domain) => (
                <button
                  key={domain.id}
                  onClick={() => handleDomainSelect(domain.id)}
                  className={`p-6 rounded-xl text-left transition-all ${
                    selectedDomain === domain.id
                      ? 'bg-blue-500/20 border-2 border-blue-500'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <domain.icon className={`w-8 h-8 mb-3 ${
                    selectedDomain === domain.id ? 'text-blue-400' : 'text-gray-400'
                  }`} />
                  <h3 className="font-medium text-white">{domain.name}</h3>
                  {domain.entities.length > 0 && (
                    <p className="text-sm text-gray-500 mt-1">
                      {domain.entities.join(', ')}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>
        );

      // Step 2: Data Model
      case 2:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Define the entities for your application. You can add, remove, or modify them.
            </p>

            {/* Entity list */}
            <div className="space-y-2">
              {entities.map((entity) => (
                <div
                  key={entity}
                  className="flex items-center justify-between px-4 py-3 bg-white/5 rounded-xl"
                >
                  <div className="flex items-center gap-3">
                    <Database className="w-4 h-4 text-blue-400" />
                    <span className="text-white">{entity}</span>
                  </div>
                  <button
                    onClick={() => handleRemoveEntity(entity)}
                    className="text-gray-500 hover:text-red-400 transition-colors"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>

            {/* Add entity */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newEntity}
                onChange={(e) => setNewEntity(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddEntity()}
                placeholder="New entity name (e.g., Order)"
                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
              <button
                onClick={handleAddEntity}
                className="px-6 py-3 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors"
              >
                Add
              </button>
            </div>
          </div>
        );

      // Step 3: Services
      case 3:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Configure OData service settings. The AI will generate appropriate service definitions.
            </p>

            <div className="space-y-4">
              <div className="p-4 bg-white/5 rounded-xl">
                <div className="flex items-center gap-3 mb-2">
                  <Server className="w-5 h-5 text-blue-400" />
                  <h3 className="font-medium text-white">OData V4 Service</h3>
                </div>
                <p className="text-sm text-gray-400">
                  Standard OData V4 protocol with CAP service definitions
                </p>
              </div>

              <div className="p-4 bg-white/5 rounded-xl">
                <div className="flex items-center gap-3 mb-2">
                  <Code2 className="w-5 h-5 text-green-400" />
                  <h3 className="font-medium text-white">Draft Enabled</h3>
                </div>
                <p className="text-sm text-gray-400">
                  Fiori Draft handling for editing scenarios
                </p>
              </div>
            </div>
          </div>
        );

      // Step 4: Fiori UI
      case 4:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Configure the SAP Fiori Elements UI appearance.
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Theme
              </label>
              <select
                value={fioriTheme}
                onChange={(e) => setFioriTheme(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="sap_horizon">SAP Horizon (Modern)</option>
                <option value="sap_fiori_3">SAP Fiori 3</option>
                <option value="sap_belize">SAP Belize</option>
              </select>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-4 bg-white/5 rounded-xl">
                <Palette className="w-6 h-6 text-purple-400 mb-2" />
                <h3 className="font-medium text-white">List Report</h3>
                <p className="text-sm text-gray-400">Table view with filters</p>
              </div>
              <div className="p-4 bg-white/5 rounded-xl">
                <FileCode className="w-6 h-6 text-cyan-400 mb-2" />
                <h3 className="font-medium text-white">Object Page</h3>
                <p className="text-sm text-gray-400">Detail view with facets</p>
              </div>
            </div>
          </div>
        );

      // Step 5: Security
      case 5:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Configure authentication and authorization settings.
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Authentication Type
              </label>
              <select
                value={authType}
                onChange={(e) => setAuthType(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="mock">Mock (Development)</option>
                <option value="xsuaa">XSUAA (SAP BTP)</option>
              </select>
            </div>

            <div className="space-y-2">
              {['Viewer', 'Editor', 'Admin'].map((role) => (
                <div
                  key={role}
                  className="flex items-center gap-3 px-4 py-3 bg-white/5 rounded-xl"
                >
                  <Shield className="w-4 h-4 text-green-400" />
                  <span className="text-white">{role}</span>
                  <span className="text-xs text-gray-500 ml-auto">
                    {role === 'Admin' ? 'Full access' : role === 'Editor' ? 'Read/Write' : 'Read only'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );

      // Step 6: Generate
      case 6:
        return (
          <div className="space-y-6">
            {!isGenerating ? (
              <>
                <div className="text-center py-8">
                  <Rocket className="w-16 h-16 text-blue-400 mx-auto mb-4" />
                  <h2 className="text-xl font-bold text-white mb-2">
                    Ready to Generate
                  </h2>
                  <p className="text-gray-400 max-w-md mx-auto">
                    Click Generate App to start the AI agents. They will create your complete SAP CAP + Fiori application.
                  </p>
                </div>

                {/* Summary */}
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="p-4 bg-white/5 rounded-xl text-center">
                    <div className="text-2xl font-bold text-white">{entities.length}</div>
                    <div className="text-sm text-gray-400">Entities</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-xl text-center">
                    <div className="text-2xl font-bold text-white">9</div>
                    <div className="text-sm text-gray-400">AI Agents</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-xl text-center">
                    <div className="text-2xl font-bold text-white">~20</div>
                    <div className="text-sm text-gray-400">Files</div>
                  </div>
                </div>
              </>
            ) : (
              <AgentProgress
                agents={AGENTS}
                executions={agentHistory}
                currentAgent={currentAgent}
              />
            )}
          </div>
        );

      // Step 7: Download
      case 7:
        return (
          <div className="space-y-6">
            <div className="text-center py-8">
              <CheckCircle2 className="w-16 h-16 text-green-400 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-white mb-2">
                Generation Complete!
              </h2>
              <p className="text-gray-400">
                Your SAP application has been generated with {getTotalFiles()} files.
              </p>
            </div>

            {/* File breakdown */}
            {result && (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { name: 'Database', count: result.artifacts_db.length, icon: Database },
                  { name: 'Services', count: result.artifacts_srv.length, icon: Server },
                  { name: 'UI', count: result.artifacts_app.length, icon: Palette },
                  { name: 'Deployment', count: result.artifacts_deployment.length, icon: Rocket },
                  { name: 'Docs', count: result.artifacts_docs.length, icon: FileCode },
                ].map((cat) => (
                  <div key={cat.name} className="p-4 bg-white/5 rounded-xl">
                    <div className="flex items-center gap-3">
                      <cat.icon className="w-5 h-5 text-blue-400" />
                      <span className="text-white">{cat.name}</span>
                      <span className="ml-auto text-gray-400">{cat.count} files</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Download button */}
            {session && (
              <div className="text-center pt-4">
                <a
                  href={getDownloadUrl(session.id)}
                  className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-green-600 to-green-500 rounded-xl font-semibold text-white hover:from-green-500 hover:to-green-400 transition-all shadow-lg shadow-green-500/25"
                >
                  <Download className="w-5 h-5" />
                  Download Project ZIP
                </a>
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <WizardLayout
      steps={STEPS}
      currentStep={currentStep}
      onStepChange={setCurrentStep}
      onNext={handleNext}
      onPrevious={handlePrevious}
      canProceed={canProceed()}
      isGenerating={isGenerating}
    >
      {renderStepContent()}
    </WizardLayout>
  );
}
