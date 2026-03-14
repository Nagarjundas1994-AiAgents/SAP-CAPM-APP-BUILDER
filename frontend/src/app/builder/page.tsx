'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import WizardLayout from '@/components/WizardLayout';
import AgentProgressEnhanced from '@/components/AgentProgressEnhanced';
import PlanReview from '@/components/PlanReview';
import ArtifactEditor from '@/components/ArtifactEditor';
import { FioriPreview } from '@/components/FioriPreview';
import ChatPanel, { ChatMessage } from '@/components/ChatPanel';
import HumanGateModal from '@/components/HumanGateModal';
import AgentDetailDrawer from '@/components/AgentDetailDrawer';
import CostTracker from '@/components/CostTracker';
import {
  createSession,
  updateSession,
  startGeneration,
  getArtifacts,
  getDownloadUrl,
  generatePlan,
  updatePlan,
  approvePlan,
  getGenerationStreamUrl,
  updateArtifact,
  sendChatPrompt,
  getChatHistory,
  getRegenerateStreamUrl,
  getConfig,
  getProviderModels,
  submitGateDecision,
  getCurrentGate,
  Session,
  GenerationResult,
  AgentExecution,
  ImplementationPlan,
  ValidationError,
  ProviderSummary,
  ModelOption,
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
  Edit3,
  Layout,
  ArrowRight,
  MessageSquare,
  Zap,
  Layers,
  Crown,
  Sparkles,
} from 'lucide-react';

// Wizard steps - now includes Plan Review
const STEPS = [
  { id: 0, name: 'Project Setup', shortName: 'Project' },
  { id: 1, name: 'Business Domain', shortName: 'Domain' },
  { id: 2, name: 'Data Model', shortName: 'Data' },
  { id: 3, name: 'DB Migration', shortName: 'DB Migration' },
  { id: 4, name: 'Integrations', shortName: 'Integrations' },
  { id: 5, name: 'Services & APIs', shortName: 'Services' },
  { id: 6, name: 'Fiori UI', shortName: 'UI' },
  { id: 7, name: 'Security', shortName: 'Security' },
  { id: 8, name: 'Review Plan', shortName: 'Plan' },
  { id: 9, name: 'Generate', shortName: 'Generate' },
  { id: 10, name: 'Download', shortName: 'Download' },
];

// Agent definitions
const AGENTS = [
  { name: 'requirements', displayName: 'Requirements Agent', description: 'Analyzing business requirements' },
  { name: 'enterprise_architecture', displayName: 'Enterprise Architecture Agent', description: 'Designing the solution blueprint' },
  { name: 'domain_modeling', displayName: 'Domain Modeling Agent', description: 'Defining business entities' },
  { name: 'data_modeling', displayName: 'Data Modeling Agent', description: 'Generating CDS schemas' },
  { name: 'db_migration', displayName: 'DB Migration Agent', description: 'Handling DB migrations and MTX' },
  { name: 'integration', displayName: 'Integration Agent', description: 'Connecting external systems' },
  { name: 'service_exposure', displayName: 'Service Exposure Agent', description: 'Creating OData services' },
  { name: 'integration_design', displayName: 'Integration Design Agent', description: 'Designing system connectivity' },
  { name: 'error_handling', displayName: 'Error Handling Agent', description: 'Configuring resilience patterns' },
  { name: 'audit_logging', displayName: 'Audit Logging Agent', description: 'Setting up audit trails' },
  { name: 'api_governance', displayName: 'API Governance Agent', description: 'Enforcing API standards' },
  { name: 'business_logic', displayName: 'Business Logic Agent', description: 'Writing event handlers' },
  { name: 'ux_design', displayName: 'UX Design Agent', description: 'Designing Fiori layouts' },
  { name: 'fiori_ui', displayName: 'Fiori UI Agent', description: 'Building Fiori Elements app' },
  { name: 'security', displayName: 'Security Agent', description: 'Configuring authorization' },
  { name: 'multitenancy', displayName: 'Multitenancy Agent', description: 'Setting up SaaS isolation' },
  { name: 'i18n', displayName: 'I18n Agent', description: 'Enabling globalization' },
  { name: 'feature_flags', displayName: 'Feature Flag Agent', description: 'Adding conditional logic' },
  { name: 'compliance_check', displayName: 'Compliance Agent', description: 'Running SAP policy checks' },
  { name: 'extension', displayName: 'Extension Agent', description: 'Adding extension points' },
  { name: 'performance_review', displayName: 'Performance Agent', description: 'Optimizing resource usage' },
  { name: 'ci_cd', displayName: 'CI/CD Agent', description: 'Generating pipeline assets' },
  { name: 'deployment', displayName: 'Deployment Agent', description: 'Creating deployment config' },
  { name: 'testing', displayName: 'Testing Agent', description: 'Generating automated tests' },
  { name: 'documentation', displayName: 'Documentation Agent', description: 'Generating technical guides' },
  { name: 'observability', displayName: 'Observability Agent', description: 'Adding health monitoring' },
  { name: 'project_assembly', displayName: 'Project Assembly Agent', description: 'Materializing the generated workspace' },
  { name: 'project_verification', displayName: 'Project Verification Agent', description: 'Running readiness checks' },
  { name: 'validation', displayName: 'Validation Agent', description: 'Final project validation' },
];

// Domain templates
const DOMAIN_TEMPLATES = [
  { id: 'hr', name: 'Human Resources', icon: Briefcase, entities: ['Employee', 'Department', 'LeaveRequest', 'TimeEntry', 'Position', 'PayGrade'] },
  { id: 'crm', name: 'Customer Relationship', icon: Briefcase, entities: ['Account', 'Contact', 'Opportunity', 'Activity', 'Lead', 'Campaign'] },
  { id: 'ecommerce', name: 'E-Commerce', icon: Palette, entities: ['Product', 'Category', 'Order', 'OrderItem', 'Customer', 'Review'] },
  { id: 'inventory', name: 'Inventory Management', icon: Database, entities: ['Product', 'Warehouse', 'InventoryLevel', 'StockMovement', 'Supplier'] },
  { id: 'finance', name: 'Finance & Accounting', icon: Server, entities: ['ExpenseReport', 'ExpenseItem', 'Budget', 'CostCenter', 'Invoice'] },
  { id: 'logistics', name: 'Logistics & Shipping', icon: Rocket, entities: ['Shipment', 'ShipmentItem', 'Route', 'Carrier', 'TrackingEvent'] },
  { id: 'custom', name: 'Custom Domain', icon: Puzzle, entities: [] },
];

const createFallbackModel = (
  id: string,
  label: string,
  pricingType: 'free' | 'paid' | 'unknown' = 'paid',
  recommended = false,
): ModelOption => ({
  id,
  name: label.replace(/\s+\(.+\)$/, ''),
  label,
  pricing_type: pricingType,
  price_summary: null,
  created_at: null,
  context_length: null,
  description: null,
  source: 'static',
  recommended,
});

const FALLBACK_PROVIDER_OPTIONS: ProviderSummary[] = [
  { id: 'openai', label: 'OpenAI', configured: false, default_model: 'gpt-5.2', catalog_type: 'static' },
  { id: 'gemini', label: 'Google Gemini', configured: false, default_model: 'gemini-1.5-pro', catalog_type: 'static' },
  { id: 'deepseek', label: 'DeepSeek', configured: false, default_model: 'deepseek-chat', catalog_type: 'static' },
  { id: 'kimi', label: 'Kimi (Moonshot)', configured: false, default_model: 'kimi-k2.5', catalog_type: 'static' },
  { id: 'xai', label: 'xAI', configured: false, default_model: 'grok-4-1-fast-reasoning', catalog_type: 'live' },
  { id: 'openrouter', label: 'OpenRouter', configured: false, default_model: null, catalog_type: 'live' },
];

const FALLBACK_MODEL_CATALOG: Record<string, ModelOption[]> = {
  openai: [
    createFallbackModel('gpt-5.2', 'GPT-5.2 (Latest - Recommended)', 'paid', true),
    createFallbackModel('gpt-5.3-codex', 'GPT-5.3 Codex (Best for Code)'),
    createFallbackModel('gpt-4o', 'GPT-4o'),
    createFallbackModel('o3', 'o3 (Best Reasoning)'),
    createFallbackModel('o3-mini', 'o3 Mini (Faster)'),
  ],
  gemini: [
    createFallbackModel('gemini-1.5-pro', 'Gemini 1.5 Pro (Latest - Recommended)', 'paid', true),
    createFallbackModel('gemini-1.5-flash', 'Gemini 1.5 Flash (Faster)'),
    createFallbackModel('gemini-2.0-flash', 'Gemini 2.0 Flash'),
  ],
  deepseek: [
    createFallbackModel('deepseek-chat', 'DeepSeek V3.2 Chat (Recommended)', 'paid', true),
    createFallbackModel('deepseek-reasoner', 'DeepSeek R1 (Best Reasoning)'),
    createFallbackModel('deepseek-coder', 'DeepSeek Coder V2'),
  ],
  kimi: [
    createFallbackModel('kimi-k2.5', 'Kimi K2.5 (Latest - Recommended)', 'paid', true),
    createFallbackModel('kimi-k2.5-thinking', 'Kimi K2.5 Thinking (Reasoning)'),
    createFallbackModel('kimi-k2', 'Kimi K2'),
  ],
  xai: [
    createFallbackModel('grok-4.20-multi-agent-beta-0309', 'Grok 4.20 Multi-Agent Beta 0309 (Paid)', 'paid', true),
    createFallbackModel('grok-4.20-beta-0309-reasoning', 'Grok 4.20 Beta 0309 Reasoning (Paid)'),
    createFallbackModel('grok-4.20-beta-0309-non-reasoning', 'Grok 4.20 Beta 0309 Non-Reasoning (Paid)'),
    createFallbackModel('grok-4-1-fast-reasoning', 'Grok 4.1 Fast Reasoning (Paid)'),
    createFallbackModel('grok-4-1-fast-non-reasoning', 'Grok 4.1 Fast Non-Reasoning (Paid)'),
    createFallbackModel('grok-code-fast-1', 'Grok Code Fast 1 (Paid)'),
    createFallbackModel('grok-4-0709', 'Grok 4 0709 (Paid)'),
    createFallbackModel('grok-3', 'Grok 3 (Paid)'),
    createFallbackModel('grok-3-mini', 'Grok 3 Mini (Paid)'),
    createFallbackModel('grok-4-fast-reasoning', 'Grok 4 Fast Reasoning (Paid)'),
    createFallbackModel('grok-4-fast-non-reasoning', 'Grok 4 Fast Non-Reasoning (Paid)'),
  ],
  openrouter: [],
};

export default function BuilderPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoadingPlan, setIsLoadingPlan] = useState(false);
  const [plan, setPlan] = useState<ImplementationPlan | null>(null);
  const [agentHistory, setAgentHistory] = useState<AgentExecution[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [showArtifactEditor, setShowArtifactEditor] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [logs, setLogs] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<'preview' | 'code' | 'logs'>('preview');
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);

  // Chat state (post-generation modification)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isChatProcessing, setIsChatProcessing] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [showChatPanel, setShowChatPanel] = useState(false);

  // Human Gate Modal state
  const [gateModalOpen, setGateModalOpen] = useState(false);
  const [currentGate, setCurrentGate] = useState<any>(null);

  // Agent Detail Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [selectedExecution, setSelectedExecution] = useState<AgentExecution | null>(null);

  // Cost Tracker state
  const [costData, setCostData] = useState({
    totalTokens: 0,
    sonnetTokens: 0,
    haikuTokens: 0,
    estimatedCost: 0,
    agentCosts: [] as Array<{
      agent_name: string;
      tokens: number;
      cost: number;
      model_tier: 'sonnet' | 'haiku';
    }>
  });

  // Form state
  const [projectName, setProjectName] = useState('');
  const [projectNamespace, setProjectNamespace] = useState('com.company');
  const [projectDescription, setProjectDescription] = useState('');
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [entities, setEntities] = useState<string[]>([]);
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [newEntity, setNewEntity] = useState('');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [llmModel, setLlmModel] = useState('gpt-5.2');
  const [providerOptions, setProviderOptions] = useState<ProviderSummary[]>(FALLBACK_PROVIDER_OPTIONS);
  const [modelCatalog, setModelCatalog] = useState<Record<string, ModelOption[]>>(FALLBACK_MODEL_CATALOG);
  const [loadedModelProviders, setLoadedModelProviders] = useState<Record<string, boolean>>({});
  const [isLoadingModelCatalog, setIsLoadingModelCatalog] = useState(false);
  const [fioriTheme, setFioriTheme] = useState('sap_horizon');
  const [fioriMainEntity, setFioriMainEntity] = useState<string>('');
  const [authType, setAuthType] = useState('mock');
  const [complexityLevel, setComplexityLevel] = useState('standard');

  const selectedProvider = providerOptions.find((provider) => provider.id === llmProvider)
    ?? FALLBACK_PROVIDER_OPTIONS.find((provider) => provider.id === llmProvider)
    ?? FALLBACK_PROVIDER_OPTIONS[0];
  const availableModels = modelCatalog[llmProvider] ?? [];
  const freeModelCount = availableModels.filter((model) => model.pricing_type === 'free').length;
  const paidModelCount = availableModels.filter((model) => model.pricing_type === 'paid').length;

  useEffect(() => {
    let isMounted = true;

    const loadConfig = async () => {
      try {
        const config = await getConfig();
        if (!isMounted || config.supported_providers.length === 0) return;

        setProviderOptions(config.supported_providers);
        
        if (config.default_provider) {
          setLlmProvider(config.default_provider);
          
          if (config.default_model) {
            setLlmModel(config.default_model);
          } else {
            const defaultProviderSpec = config.supported_providers.find((p: ProviderSummary) => p.id === config.default_provider);
            if (defaultProviderSpec?.default_model) {
              setLlmModel(defaultProviderSpec.default_model);
            }
          }
        }
      } catch (error) {
        console.error('Failed to load provider configuration:', error);
      }
    };

    void loadConfig();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (loadedModelProviders[llmProvider]) {
      return;
    }

    let isMounted = true;

    const loadModels = async () => {
      setIsLoadingModelCatalog(true);
      try {
        const response = await getProviderModels(llmProvider);
        if (!isMounted) return;

        if (response.models.length > 0) {
          setModelCatalog((prev) => ({
            ...prev,
            [llmProvider]: response.models,
          }));
        }
      } catch (error) {
        console.error(`Failed to load models for ${llmProvider}:`, error);
      } finally {
        if (isMounted) {
          setLoadedModelProviders((prev) => ({
            ...prev,
            [llmProvider]: true,
          }));
          setIsLoadingModelCatalog(false);
        }
      }
    };

    void loadModels();

    return () => {
      isMounted = false;
    };
  }, [llmProvider, loadedModelProviders]);

  useEffect(() => {
    if (availableModels.length === 0) {
      return;
    }

    const currentModelStillAvailable = availableModels.some((model) => model.id === llmModel);
    if (currentModelStillAvailable) {
      return;
    }

    const recommendedModel = availableModels.find((model) => model.recommended) ?? availableModels[0];
    setLlmModel(recommendedModel.id);
  }, [availableModels, llmModel]);
  
  // Polling fallback for Human Gates (ensures visibility even if SSE is unreliable)
  useEffect(() => {
    if (!session || !isGenerating || gateModalOpen) return;

    const pollInterval = setInterval(async () => {
      try {
        const gateStatus = await getCurrentGate(session.id);
        if (gateStatus.gate_id && !gateModalOpen) {
          console.log('🔄 Polling detected active gate:', gateStatus.gate_id);
          setCurrentGate({
            gate_id: gateStatus.gate_id,
            gate_name: gateStatus.gate_name,
            context: gateStatus.context,
            session_id: session.id
          });
          setGateModalOpen(true);
        }
      } catch (error) {
        console.error('Failed to poll gate status:', error);
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(pollInterval);
  }, [session, isGenerating, gateModalOpen]);

  // Validation
  const canProceed = () => {
    switch (currentStep) {
      case 0:
        return projectName.trim().length >= 3;
      case 1:
        return selectedDomain !== null;
      case 2:
        return entities.length > 0;
      case 3: // DB Migration
      case 4: // Integrations
      case 5:
      case 6:
      case 7:
        return true;
      case 8:
        return plan !== null && plan.approved;
      case 9:
        return !isGenerating;
      case 10:
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

    if (currentStep === 7 && !plan) {
      // Generate implementation plan when moving to Plan Review
      try {
        setIsLoadingPlan(true);
        // First update session with current configuration
        if (session) {
          await updateSession(session.id, {
            configuration: {
              domain: selectedDomain,
              entities: entities.map((name) => ({ name, fields: [] })),
              integrations: integrations,
              llm_provider: llmProvider,
              llm_model: llmModel,
              fiori_theme: fioriTheme,
              auth_type: authType,
              fiori_main_entity: entities[0] || 'Entity',
              complexity_level: complexityLevel,
            },
          });
          const generatedPlan = await generatePlan(session.id);
          setPlan(generatedPlan);
        }
      } catch (error) {
        console.error('Failed to generate plan:', error);
        return;
      } finally {
        setIsLoadingPlan(false);
      }
    }

    if (currentStep === 9) {
      // Start generation (plan is already approved)
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

  // Handle generation using streaming SSE
  const handleGenerate = async () => {
    if (!session) return;

    setIsGenerating(true);
    setAgentHistory([]);
    setCurrentAgent('requirements');
    setLogs({});
    setValidationErrors([]);

    try {
      // Create EventSource connection
      const streamUrl = getGenerationStreamUrl(session.id);
      const eventSource = new EventSource(streamUrl);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('Stream event:', data.type, data);
          
          if (data.type === 'connected') {
            console.log('Stream connected for session:', data.session_id);
          } else if (data.type === 'agent_start') {
            setCurrentAgent(data.agent);
          } else if (data.type === 'agent_log') {
            setLogs(prev => ({
              ...prev,
              [data.agent]: (prev[data.agent] || '') + `[${new Date(data.timestamp).toLocaleTimeString()}] ${data.message}\n`
            }));
          } else if (data.type === 'agent_complete') {
            setAgentHistory(data.agent_history);
            setValidationErrors(data.validation_errors || []);
            
            // Just clear current agent, next agent will be set by agent_start event
            setCurrentAgent(null);
          } else if (data.type === 'human_gate_pending') {
            // Human gate triggered - show modal
            console.log('🚪 Human gate triggered:', data.gate_name, data);
            setCurrentGate({
              gate_id: data.gate_id,
              gate_name: data.gate_name,
              context: data.context,
              session_id: session.id
            });
            setGateModalOpen(true);
            console.log('✅ Gate modal opened');
          } else if (data.type === 'workflow_complete') {
            console.log('Workflow complete, closing stream');
            eventSource.close();
            setAgentHistory(data.agent_history);
            setCurrentAgent(null);
            setIsGenerating(false);
            
            // Get artifacts after completion
            getArtifacts(session.id).then(artifacts => {
              setResult(artifacts);
              setCurrentStep(10); // Go to download step
            });
          } else if (data.type === 'workflow_error' || data.type === 'error') {
            console.error('Generation failed:', data.error || data.message);
            eventSource.close();
            setIsGenerating(false);
          }
        } catch (e) {
          console.error('Failed to parse stream event:', e);
        }
      };

      eventSource.onerror = (error) => {
        if (eventSource.readyState === EventSource.CLOSED) {
          console.log('Stream closed normally');
        } else {
          console.error('EventSource encountered an error:', error);
          eventSource.close();
          setIsGenerating(false);
        }
      };
    } catch (error) {
      console.error('Streaming generation failed:', error);
      setIsGenerating(false);
    }
  };

  // Handle gate decision
  const handleGateDecision = async (decision: 'approve' | 'refine', refinementNotes?: string, targetAgent?: string) => {
    if (!session || !currentGate) return;

    try {
      await submitGateDecision(
        session.id,
        currentGate.gate_id,
        decision,
        refinementNotes,
        targetAgent
      );

      // Close modal and continue generation
      setGateModalOpen(false);
      setCurrentGate(null);
    } catch (error) {
      console.error('Failed to submit gate decision:', error);
      throw error;
    }
  };

  // Handle plan update
  const handlePlanUpdate = async (updates: Partial<ImplementationPlan>) => {
    if (!session || !plan) return;
    try {
      const updatedPlan = await updatePlan(session.id, updates as any);
      setPlan(updatedPlan);
    } catch (error) {
      console.error('Failed to update plan:', error);
    }
  };

  // Handle plan approval
  const handlePlanApprove = async () => {
    if (!session) return;
    try {
      setIsLoadingPlan(true);
      const approvedPlan = await approvePlan(session.id);
      setPlan(approvedPlan);
      if (approvedPlan.entities.length > 0) {
        setFioriMainEntity(approvedPlan.entities[0].name);
      }
      setCurrentStep(currentStep + 1); // Go to Generate step
    } catch (error) {
      console.error('Failed to approve plan:', error);
    } finally {
      setIsLoadingPlan(false);
    }
  };

  // Handle plan regeneration
  const handlePlanRegenerate = async () => {
    if (!session) return;
    try {
      setIsLoadingPlan(true);
      const newPlan = await generatePlan(session.id);
      setPlan(newPlan);
    } catch (error) {
      console.error('Failed to regenerate plan:', error);
    } finally {
      setIsLoadingPlan(false);
    }
  };

  // Handle artifact save
  const handleArtifactSave = async (path: string, content: string) => {
    if (!session) return;
    try {
      await updateArtifact(session.id, path, content);
    } catch (error) {
      console.error('Failed to update artifact:', error);
      throw error;
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

  // === Chat Handlers (post-generation modification) ===
  const handleChatSend = async (message: string) => {
    if (!session) return;

    // Add user message optimistically
    const userMsg: ChatMessage = {
      role: 'user',
      message,
      timestamp: new Date().toISOString(),
    };
    setChatMessages(prev => [...prev, userMsg]);
    setIsChatProcessing(true);

    try {
      const response = await sendChatPrompt(session.id, message);

      // Add assistant response
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        message: response.message,
        entities_preview: response.entities_preview,
        suggested_followups: response.suggested_followups,
        timestamp: response.timestamp,
      };
      setChatMessages(prev => [...prev, assistantMsg]);

      // Update the plan entities for live preview
      if (response.entities_preview && response.entities_preview.length > 0) {
        setPlan(prev => prev ? {
          ...prev,
          entities: response.entities_preview as any,
        } : prev);
        // Update entity list for other UI elements
        setEntities(response.entities_preview.map((e: any) => e.name));
        if (response.entities_preview.length > 0) {
          setFioriMainEntity(response.entities_preview[0].name);
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errMsg: ChatMessage = {
        role: 'assistant',
        message: `Sorry, something went wrong: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        timestamp: new Date().toISOString(),
      };
      setChatMessages(prev => [...prev, errMsg]);
    } finally {
      setIsChatProcessing(false);
    }
  };

  const handleRegenerate = async () => {
    if (!session) return;

    setIsRegenerating(true);
    setAgentHistory([]);
    setCurrentAgent('requirements');
    setLogs({});
    setValidationErrors([]);

    try {
      const streamUrl = getRegenerateStreamUrl(session.id);
      const response = await fetch(streamUrl, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Failed to start regeneration');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error('No response body');

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'agent_start') {
              setCurrentAgent(data.agent);
            } else if (data.type === 'agent_complete') {
              setAgentHistory(data.agent_history || []);
            } else if (data.type === 'workflow_complete') {
              setAgentHistory(data.agent_history || []);
              setCurrentAgent(null);
              const artifacts = await getArtifacts(session.id);
              setResult(artifacts);
              // Add system message about successful regeneration
              const sysMsg: ChatMessage = {
                role: 'assistant',
                message: '✅ App regenerated successfully! The preview and artifacts have been updated with your changes.',
                timestamp: new Date().toISOString(),
                suggested_followups: ['Make more changes', 'Download the project'],
              };
              setChatMessages(prev => [...prev, sysMsg]);
            } else if (data.type === 'error' || data.type === 'workflow_error') {
              console.error('Regeneration error:', data.message || data.error);
              const errMsg: ChatMessage = {
                role: 'assistant',
                message: `❌ Regeneration failed: ${data.message || data.error}`,
                timestamp: new Date().toISOString(),
              };
              setChatMessages(prev => [...prev, errMsg]);
            }
          } catch (e) {
            // skip unparseable lines
          }
        }
      }
    } catch (error) {
      console.error('Regeneration failed:', error);
      const errMsg: ChatMessage = {
        role: 'assistant',
        message: `❌ Regeneration failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      };
      setChatMessages(prev => [...prev, errMsg]);
    } finally {
      setIsRegenerating(false);
    }
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
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                {providerOptions.map((provider) => (
                  <option key={provider.id} value={provider.id} className="bg-gray-900 text-white">
                    {provider.label}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-gray-500">
                {selectedProvider.configured
                  ? `${selectedProvider.label} is configured and ready to use.`
                  : `${selectedProvider.label} is visible in the builder, but you still need its API key in .env before generation can use it.`}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Model
              </label>
              <select
                value={availableModels.length === 0 ? '' : llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                {availableModels.length === 0 && (
                  <option value="" className="bg-gray-900 text-white">
                    No models available
                  </option>
                )}
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id} className="bg-gray-900 text-white">
                    {model.label}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-gray-500">
                {isLoadingModelCatalog
                  ? 'Loading the latest model catalog...'
                  : llmProvider === 'openrouter'
                    ? `Showing ${availableModels.length} OpenRouter text models from Jan 2025 onward (${freeModelCount} free, ${paidModelCount} paid).`
                    : llmProvider === 'xai'
                      ? `Showing ${availableModels.length} current xAI text models from the official xAI model catalog.`
                      : `Showing ${availableModels.length} model options for ${selectedProvider.label}.`}
              </p>
            </div>

            {/* Complexity Level */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                App Complexity Level
              </label>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { id: 'starter', name: 'Starter', icon: Zap, entities: '2-3', desc: 'Basic CRUD, mock auth', badge: '' },
                  { id: 'standard', name: 'Standard', icon: Layers, entities: '4-6', desc: 'Draft, validations, roles', badge: 'Recommended' },
                  { id: 'enterprise', name: 'Enterprise', icon: Crown, entities: '6-10', desc: 'Workflows, analytics', badge: 'Popular' },
                  { id: 'full_stack', name: 'Full Stack', icon: Sparkles, entities: '8-15', desc: 'Everything + CI/CD', badge: 'Max' },
                ].map((level) => (
                  <button
                    key={level.id}
                    onClick={() => setComplexityLevel(level.id)}
                    className={`relative p-4 rounded-xl text-left transition-all border ${
                      complexityLevel === level.id
                        ? level.id === 'starter' ? 'bg-emerald-500/20 border-emerald-500 ring-1 ring-emerald-500/50'
                          : level.id === 'standard' ? 'bg-blue-500/20 border-blue-500 ring-1 ring-blue-500/50'
                          : level.id === 'enterprise' ? 'bg-purple-500/20 border-purple-500 ring-1 ring-purple-500/50'
                          : 'bg-amber-500/20 border-amber-500 ring-1 ring-amber-500/50'
                        : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                    }`}
                  >
                    {level.badge && (
                      <span className={`absolute -top-2 -right-2 text-[10px] px-2 py-0.5 rounded-full font-bold ${
                        level.id === 'standard' ? 'bg-blue-500 text-white' :
                        level.id === 'enterprise' ? 'bg-purple-500 text-white' :
                        'bg-amber-500 text-black'
                      }`}>{level.badge}</span>
                    )}
                    <level.icon className={`w-6 h-6 mb-2 ${
                      complexityLevel === level.id
                        ? level.id === 'starter' ? 'text-emerald-400'
                          : level.id === 'standard' ? 'text-blue-400'
                          : level.id === 'enterprise' ? 'text-purple-400'
                          : 'text-amber-400'
                        : 'text-gray-400'
                    }`} />
                    <div className="font-medium text-white text-sm">{level.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{level.entities} entities</div>
                    <div className="text-xs text-gray-500">{level.desc}</div>
                  </button>
                ))}
              </div>
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

      // Step 3: DB Migration
      case 3:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Configure database migration and multi-tenancy settings.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-6 rounded-xl bg-white/5 border border-white/10">
                <h3 className="font-medium text-white mb-2">HANA Native Artifacts</h3>
                <p className="text-sm text-gray-500 mb-4">
                  Generate HANA-specific schemas, calculation views, and roles (.hdbview, .hdbrole).
                </p>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={true}
                    disabled
                    className="w-5 h-5 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                  />
                  <span className="text-white">Enabled by DB Migration Agent</span>
                </label>
              </div>

              <div className="p-6 rounded-xl bg-white/5 border border-white/10">
                <h3 className="font-medium text-white mb-2">Multi-Tenancy (MTX)</h3>
                <p className="text-sm text-gray-500 mb-4">
                  Support SAP BTP multi-tenant database patterns and SaaS provisioning.
                </p>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={true}
                    disabled
                    className="w-5 h-5 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                  />
                  <span className="text-white">Enabled by DB Migration Agent</span>
                </label>
              </div>
            </div>
          </div>
        );

      // Step 4: Integrations
      case 4:
        return (
          <div className="space-y-6">
            <p className="text-gray-400">
              Connect your application to external enterprise systems like SAP S/4HANA or SuccessFactors.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              {[
                { id: 's4hana_bp', name: 'S/4HANA Business Partner API', system: 'S4HANA', icon: Server, desc: 'Read/Write Business Partners from S/4HANA' },
                { id: 's4hana_product', name: 'S/4HANA Product Master API', system: 'S4HANA', icon: Database, desc: 'Read Product data from S/4HANA' },
                { id: 'sf_emp', name: 'SuccessFactors Employee Central', system: 'SuccessFactors', icon: Briefcase, desc: 'Read Employee profiles from SuccessFactors' },
              ].map((template) => {
                const isSelected = integrations.some(i => i.id === template.id);
                return (
                  <button
                    key={template.id}
                    onClick={() => {
                      if (isSelected) {
                        setIntegrations(integrations.filter(i => i.id !== template.id));
                      } else {
                        setIntegrations([...integrations, { id: template.id, name: template.name, system: template.system, endpoint: '', auth_type: 'OAuth2' }]);
                      }
                    }}
                    className={`p-4 rounded-xl text-left transition-all relative overflow-hidden ${
                      isSelected
                        ? 'bg-blue-500/20 border-2 border-blue-500'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute top-3 right-3 text-blue-400">
                        <CheckCircle2 className="w-5 h-4" />
                      </div>
                    )}
                    <template.icon className={`w-6 h-6 mb-3 ${isSelected ? 'text-blue-400' : 'text-gray-400'}`} />
                    <h3 className="font-medium text-white text-sm">{template.name}</h3>
                    <p className="text-xs text-gray-500 mt-1">{template.desc}</p>
                  </button>
                );
              })}
            </div>
            
            {integrations.length > 0 && (
              <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                <h4 className="text-sm font-medium text-blue-400 mb-2">Selected Integrations</h4>
                <ul className="text-sm text-gray-300 space-y-1">
                  {integrations.map(i => (
                    <li key={i.id} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                      {i.name} ({i.system})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );

      // Step 5: Services
      case 5:
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

      // Step 6: Fiori UI
      case 6:
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
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="sap_horizon" className="bg-gray-900 text-white">SAP Horizon (Modern)</option>
                <option value="sap_fiori_3" className="bg-gray-900 text-white">SAP Fiori 3</option>
                <option value="sap_belize" className="bg-gray-900 text-white">SAP Belize</option>
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

      // Step 7: Security
      case 7:
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
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value="mock" className="bg-gray-900 text-white">Mock (Development)</option>
                <option value="xsuaa" className="bg-gray-900 text-white">XSUAA (SAP BTP)</option>
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

      // Step 8: Plan Review
      case 8:
        return (
          <div className="space-y-6">
            {isLoadingPlan ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-gray-400">Generating implementation plan...</p>
              </div>
            ) : plan ? (
              <PlanReview
                plan={plan}
                onUpdate={handlePlanUpdate}
                onApprove={handlePlanApprove}
                onRegenerate={handlePlanRegenerate}
                isLoading={isLoadingPlan}
              />
            ) : (
              <div className="text-center py-12">
                <p className="text-red-400">Failed to load plan. Please go back and try again.</p>
              </div>
            )}
          </div>
        );

      // Step 9: Generate
      case 9:
        return (
          <div className="space-y-6">
            {isGenerating ? (
              <div className="grid lg:grid-cols-2 gap-8 items-start">
                <AgentProgressEnhanced
                  agents={AGENTS}
                  executions={agentHistory}
                  currentAgent={currentAgent}
                  logs={logs}
                />
                <div className="hidden lg:block">
                  <div className="mb-3 flex items-center gap-2 text-sm text-gray-400">
                    <Layout className="w-4 h-4 text-blue-400" />
                    <span>Real-time App Preview</span>
                  </div>
                  <FioriPreview 
                    entities={plan?.entities || []} 
                    mainEntityName={fioriMainEntity} 
                    projectName={projectName} 
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-6">
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
                <div className="grid md:grid-cols-3 gap-4 mb-8">
                  <div className="p-4 bg-white/5 rounded-xl text-center border border-white/5">
                    <div className="text-2xl font-bold text-white">{entities.length}</div>
                    <div className="text-sm text-gray-400">Entities</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-xl text-center border border-white/5">
                    <div className="text-2xl font-bold text-white">{AGENTS.length}</div>
                    <div className="text-sm text-gray-400">AI Agents</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-xl text-center border border-white/5">
                    <div className="text-2xl font-bold text-white">~20</div>
                    <div className="text-sm text-gray-400">Files</div>
                  </div>
                </div>

                <div className="flex justify-center">
                  <button
                    onClick={handleGenerate}
                    className="flex items-center gap-3 px-10 py-5 bg-gradient-to-r from-blue-600 to-blue-500 rounded-2xl font-bold text-white hover:from-blue-500 hover:to-blue-400 transition-all shadow-xl shadow-blue-500/25 group scale-105 hover:scale-110 active:scale-100"
                  >
                    <Rocket className="w-6 h-6 group-hover:rotate-12 transition-transform" />
                    <span>Generate App</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>
              </div>
            )}
          </div>
        );

      // Step 10: Download & Modify
      case 10:
        return (
          <div className="space-y-6">
            <div className="text-center py-6">
              <CheckCircle2 className="w-14 h-14 text-green-400 mx-auto mb-3" />
              <h2 className="text-xl font-bold text-white mb-2">
                Generation Complete!
              </h2>
              <p className="text-gray-400">
                Your SAP application has been generated with {getTotalFiles()} files.
              </p>
              {result?.workspace_path && (
                <p className="text-xs text-gray-500 mt-2">
                  Workspace materialized at: {result.workspace_path}
                </p>
              )}
            </div>

            {/* Tabbed View: Files vs Preview vs Chat */}
            <div className="flex justify-center mb-6">
              <div className="flex bg-white/5 p-1 rounded-xl border border-white/10">
                <button
                  onClick={() => { setShowPreview(false); setShowChatPanel(false); }}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                    !showPreview && !showChatPanel ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4" />
                    Artifacts
                  </div>
                </button>
                <button
                  onClick={() => { setShowPreview(true); setShowChatPanel(false); }}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                    showPreview && !showChatPanel ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Layout className="w-4 h-4" />
                    Preview
                  </div>
                </button>
                <button
                  onClick={() => { setShowChatPanel(true); setShowPreview(false); }}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                    showChatPanel ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" />
                    Modify with AI
                    <span className="text-[10px] px-1.5 py-0.5 bg-white/20 rounded-full">✨</span>
                  </div>
                </button>
              </div>
            </div>

            {/* Content area */}
            {showChatPanel && session ? (
              /* Chat + Preview split layout */
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="h-[600px]">
                  <ChatPanel
                    sessionId={session.id}
                    messages={chatMessages}
                    onSendMessage={handleChatSend}
                    onRegenerate={handleRegenerate}
                    isProcessing={isChatProcessing}
                    isRegenerating={isRegenerating}
                  />
                </div>
                <div className="h-[600px] overflow-auto">
                  <FioriPreview
                    entities={plan?.entities || []}
                    mainEntityName={fioriMainEntity}
                    projectName={projectName}
                  />
                </div>
              </div>
            ) : result && (
              /* File breakdown / Preview */
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                {!showPreview ? (
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
                ) : (
                  <div className="max-w-5xl mx-auto">
                    <FioriPreview
                      entities={plan?.entities || []}
                      mainEntityName={fioriMainEntity}
                      projectName={projectName}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Action buttons */}
            {session && (
              <div className="flex flex-col items-center gap-4 pt-4">
                {result?.verification_summary && (
                  <div className="px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-sm text-gray-300">
                    Verification: {result.verification_summary.passed ?? 0} passed, {result.verification_summary.failed ?? 0} failed, {result.verification_summary.warnings ?? 0} warnings
                  </div>
                )}
                <div className="flex items-center gap-4 flex-wrap justify-center">
                  <button
                    onClick={() => setShowArtifactEditor(true)}
                    className="flex items-center gap-2 px-6 py-4 bg-white/5 border border-white/10 rounded-xl font-medium text-white hover:bg-white/10 transition-all"
                  >
                    <Edit3 className="w-5 h-5 text-blue-400" />
                    Review & Edit Files
                  </button>
                  {!showChatPanel && (
                    <button
                      onClick={() => { setShowChatPanel(true); setShowPreview(false); }}
                      className="flex items-center gap-2 px-6 py-4 bg-gradient-to-r from-purple-600/20 to-blue-600/20 border border-purple-500/30 rounded-xl font-medium text-white hover:from-purple-600/30 hover:to-blue-600/30 transition-all"
                    >
                      <MessageSquare className="w-5 h-5 text-purple-400" />
                      Modify with AI ✨
                    </button>
                  )}
                  <a
                    href={getDownloadUrl(session.id)}
                    className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-green-600 to-green-500 rounded-xl font-semibold text-white hover:from-green-500 hover:to-green-400 transition-all shadow-lg shadow-green-500/25"
                  >
                    <Download className="w-5 h-5" />
                    Download Project ZIP
                  </a>
                </div>
                <p className="text-xs text-gray-500 italic">
                  Tip: Use "Modify with AI" to refine your app, then regenerate and download.
                </p>
              </div>
            )}

            {/* Artifact Editor Modal */}
            {showArtifactEditor && result && (
              <ArtifactEditor
                result={result}
                onSave={handleArtifactSave}
                onClose={() => setShowArtifactEditor(false)}
              />
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <>
      <WizardLayout
        steps={STEPS}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        onNext={handleNext}
        onPrevious={handlePrevious}
        canProceed={canProceed()}
        isGenerating={isGenerating}
        isFullWidth={currentStep === 8 || currentStep === 9}
      >
        {renderStepContent()}
      </WizardLayout>

      {/* Cost Tracker */}
      {session && isGenerating && (
        <CostTracker
          sessionId={session.id}
          totalTokens={costData.totalTokens}
          sonnetTokens={costData.sonnetTokens}
          haikuTokens={costData.haikuTokens}
          estimatedCost={costData.estimatedCost}
          agentCosts={costData.agentCosts}
        />
      )}

      {/* Agent Detail Drawer */}
      <AgentDetailDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        agent={selectedAgent}
        execution={selectedExecution}
        modelTier={selectedAgent ? (
          ['enterprise_architecture', 'domain_modeling', 'business_logic', 'validation', 'security', 'compliance_check'].includes(selectedAgent.name)
            ? 'sonnet'
            : 'haiku'
        ) : 'haiku'}
        ragDocs={[]}
        validationRules={[]}
        tokenUsage={selectedExecution ? {
          input: 0,
          output: 0,
          total: 0,
          cost: 0
        } : undefined}
      />

      {/* Human Gate Modal */}
      <HumanGateModal
        isOpen={gateModalOpen}
        onClose={() => setGateModalOpen(false)}
        gateData={currentGate}
        onDecision={handleGateDecision}
      />
    </>
  );
}
