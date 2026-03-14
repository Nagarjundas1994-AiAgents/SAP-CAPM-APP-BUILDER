# Artifact Flow Diagram
**How Generated Artifacts Reach the Frontend**

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                             │
│  (Frontend: Builder Wizard - 10 Steps)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 1. User completes wizard
                             │    - Project setup
                             │    - Domain selection
                             │    - Entity definition
                             │    - Configuration
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API: POST /api/builder/{session_id}/generate     │
│                    (backend/api/builder.py)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 2. Creates BuilderState
                             │    - Merges user config
                             │    - Sets LLM provider
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LANGGRAPH WORKFLOW (backend/agents/graph.py)            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  28 AI Agents Execute in Sequence/Parallel                   │   │
│  │                                                               │   │
│  │  1. Requirements Agent                                        │   │
│  │  2. Enterprise Architecture Agent                             │   │
│  │  3. Domain Modeling Agent                                     │   │
│  │  4. Data Modeling Agent ──────────► artifacts_db[]           │   │
│  │  5. DB Migration Agent                                        │   │
│  │  6. Integration Agent                                         │   │
│  │  7. Service Exposure Agent ───────► artifacts_srv[]          │   │
│  │  8. Integration Design Agent                                  │   │
│  │  9. Error Handling Agent                                      │   │
│  │  10. Audit Logging Agent                                      │   │
│  │  11. API Governance Agent                                     │   │
│  │  12. Business Logic Agent ────────► artifacts_srv[]          │   │
│  │  13. UX Design Agent                                          │   │
│  │  14. Fiori UI Agent ───────────────► artifacts_app[]         │   │
│  │  15. Security Agent                                           │   │
│  │  16. Multitenancy Agent                                       │   │
│  │  17. I18n Agent                                               │   │
│  │  18. Feature Flags Agent                                      │   │
│  │  19. Compliance Check Agent                                   │   │
│  │  20. Extension Agent                                          │   │
│  │  21. Performance Review Agent                                 │   │
│  │  22. CI/CD Agent                                              │   │
│  │  23. Deployment Agent ─────────────► artifacts_deployment[]  │   │
│  │  24. Testing Agent                                            │   │
│  │  25. Documentation Agent ──────────► artifacts_docs[]        │   │
│  │  26. Observability Agent                                      │   │
│  │  27. Project Assembly Agent ───────► Materializes workspace  │   │
│  │  28. Project Verification Agent                               │   │
│  │  29. Validation Agent                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Each agent generates files and stores them in BuilderState:         │
│  - artifacts_db: CDS schemas, common types                           │
│  - artifacts_srv: OData services, handlers                           │
│  - artifacts_app: Fiori Elements apps                                │
│  - artifacts_deployment: mta.yaml, package.json                      │
│  - artifacts_docs: README, guides                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 3. Workflow completes
                             │    - final_state contains all artifacts
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE PERSISTENCE                              │
│  (backend/models.py - Session table)                                 │
│                                                                       │
│  session.configuration = {                                           │
│    "artifacts_db": [...],        # List of {path, content, type}    │
│    "artifacts_srv": [...],                                           │
│    "artifacts_app": [...],                                           │
│    "artifacts_deployment": [...],                                    │
│    "artifacts_docs": [...],                                          │
│    "agent_history": [...],                                           │
│    "validation_errors": [...],                                       │
│    "generated_workspace_path": "/path/to/workspace",                 │
│    "verification_summary": {...}                                     │
│  }                                                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 4. Frontend polls or receives SSE event
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              API: GET /api/builder/{session_id}/artifacts            │
│              (backend/api/builder.py)                                │
│                                                                       │
│  Returns GenerationResult:                                           │
│  {                                                                    │
│    "session_id": "...",                                              │
│    "status": "completed",                                            │
│    "artifacts_db": [                                                 │
│      {"path": "db/schema.cds", "content": "...", "file_type": "cds"}│
│    ],                                                                 │
│    "artifacts_srv": [...],                                           │
│    "artifacts_app": [...],                                           │
│    "artifacts_deployment": [...],                                    │
│    "artifacts_docs": [...],                                          │
│    "workspace_path": "/path/to/workspace"                            │
│  }                                                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 5. Frontend receives artifacts
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND DISPLAY (Step 10)                        │
│  (frontend/src/app/builder/page.tsx)                                 │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tab 1: ARTIFACTS VIEW                                         │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  File Breakdown by Category                              │  │  │
│  │  │  ✅ Database (db/)       - 5 files                       │  │  │
│  │  │  ✅ Services (srv/)      - 8 files                       │  │  │
│  │  │  ✅ UI (app/)            - 12 files                      │  │  │
│  │  │  ✅ Deployment (/)       - 3 files                       │  │  │
│  │  │  ✅ Documentation (docs/) - 2 files                      │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  [View Code] [Preview UI] [Modify with AI]                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tab 2: CODE EDITOR (ArtifactEditor.tsx)                      │  │
│  │  ┌─────────────────┬───────────────────────────────────────┐  │  │
│  │  │ File Explorer   │  Monaco Editor                         │  │  │
│  │  │                 │                                         │  │  │
│  │  │ 📁 db/          │  namespace com.company.app;            │  │  │
│  │  │   📐 schema.cds │                                         │  │  │
│  │  │   📐 common.cds │  entity Product {                      │  │  │
│  │  │                 │    key ID : UUID;                      │  │  │
│  │  │ 📁 srv/         │    name : String(100);                 │  │  │
│  │  │   📜 service.js │    price : Decimal(10,2);             │  │  │
│  │  │   📐 service.cds│  }                                     │  │  │
│  │  │                 │                                         │  │  │
│  │  │ 📁 app/         │  [Save Changes]                        │  │  │
│  │  │   🌐 manifest...│                                         │  │  │
│  │  └─────────────────┴───────────────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  Component: ProjectTree.tsx + ArtifactEditor.tsx              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tab 3: LIVE PREVIEW (FioriPreview.tsx)                       │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  ┌─────────────────────────────────────────────────┐    │  │  │
│  │  │  │  My SAP App                          [User] ▼   │    │  │  │
│  │  │  ├─────────────────────────────────────────────────┤    │  │  │
│  │  │  │  Products                                        │    │  │  │
│  │  │  │  ┌──────────────────────────────────────────┐  │    │  │  │
│  │  │  │  │ Search...                    [+ Create]  │  │    │  │  │
│  │  │  │  ├──────────────────────────────────────────┤  │    │  │  │
│  │  │  │  │ ID    │ Name      │ Price    │ Status   │  │    │  │  │
│  │  │  │  ├──────────────────────────────────────────┤  │    │  │  │
│  │  │  │  │ 001   │ Product A │ $99.99   │ Active   │  │    │  │  │
│  │  │  │  │ 002   │ Product B │ $149.99  │ Active   │  │    │  │  │
│  │  │  │  └──────────────────────────────────────────┘  │    │  │  │
│  │  │  └─────────────────────────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  Interactive Fiori Elements UI Preview                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tab 4: AI MODIFICATION (ChatPanel.tsx)                       │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  💬 Chat with AI to modify your app                      │  │  │
│  │  │                                                            │  │  │
│  │  │  User: Add a description field to Product                │  │  │
│  │  │  AI: ✅ I've added a description field (String(500))     │  │  │
│  │  │      to the Product entity. Would you like me to:        │  │  │
│  │  │      • Add it to the UI                                   │  │  │
│  │  │      • Make it required                                   │  │  │
│  │  │      • Regenerate the app                                 │  │  │
│  │  │                                                            │  │  │
│  │  │  [Type your message...]                [Regenerate App]  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  Component: ChatPanel.tsx                                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  [Download Project ZIP]                                              │
└─────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 6. User downloads
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              API: GET /api/builder/{session_id}/download             │
│              (backend/api/builder.py)                                │
│                                                                       │
│  Creates ZIP file containing:                                        │
│  - All artifacts from database                                       │
│  - Materialized workspace (if exists)                                │
│  - Fallback files (package.json, README.md)                          │
│                                                                       │
│  Returns: StreamingResponse (application/zip)                        │
└─────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ 7. Browser downloads ZIP
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    USER'S LOCAL MACHINE                              │
│                                                                       │
│  my-sap-app.zip                                                      │
│  ├── db/                                                             │
│  │   ├── schema.cds                                                  │
│  │   └── common.cds                                                  │
│  ├── srv/                                                            │
│  │   ├── service.cds                                                 │
│  │   ├── service.js                                                  │
│  │   └── annotations.cds                                             │
│  ├── app/                                                            │
│  │   └── product/                                                    │
│  │       └── webapp/                                                 │
│  │           ├── manifest.json                                       │
│  │           ├── Component.js                                        │
│  │           └── i18n/                                               │
│  ├── package.json                                                    │
│  ├── mta.yaml                                                        │
│  ├── xs-security.json                                                │
│  └── README.md                                                       │
│                                                                       │
│  User can now:                                                       │
│  1. Extract the ZIP                                                  │
│  2. Run: npm install                                                 │
│  3. Run: cds watch                                                   │
│  4. Open: http://localhost:4004                                      │
└───────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Agent Generation (Backend)
- **Location:** `backend/agents/`
- **Files:** 28 agent files (requirements.py, data_modeling.py, fiori_ui.py, etc.)
- **Output:** Populates `BuilderState` with artifacts

### 2. State Management
- **Location:** `backend/agents/state.py`
- **Structure:** `BuilderState` TypedDict with artifact arrays
- **Persistence:** Saved to database `Session.configuration` JSON field

### 3. API Layer
- **Location:** `backend/api/builder.py`
- **Endpoints:**
  - `POST /api/builder/{session_id}/generate` - Start generation
  - `GET /api/builder/{session_id}/generate/stream` - SSE streaming
  - `GET /api/builder/{session_id}/artifacts` - Get all artifacts
  - `PUT /api/builder/{session_id}/artifacts` - Update artifact
  - `GET /api/builder/{session_id}/download` - Download ZIP

### 4. Frontend Display
- **Location:** `frontend/src/`
- **Components:**
  - `app/builder/page.tsx` - Main wizard (Step 10 shows artifacts)
  - `components/ProjectTree.tsx` - File tree navigation
  - `components/ArtifactEditor.tsx` - Monaco code editor
  - `components/FioriPreview.tsx` - Live UI preview
  - `components/ChatPanel.tsx` - AI modification interface

## Artifact Categories

| Category | Location | File Types | Example Files |
|----------|----------|------------|---------------|
| **Database** | `artifacts_db` | .cds | schema.cds, common.cds |
| **Services** | `artifacts_srv` | .cds, .js | service.cds, service.js, annotations.cds |
| **UI** | `artifacts_app` | .json, .js, .html | manifest.json, Component.js, index.html |
| **Deployment** | `artifacts_deployment` | .yaml, .json | mta.yaml, package.json, xs-security.json |
| **Documentation** | `artifacts_docs` | .md | README.md, ARCHITECTURE.md, API.md |

## Real-Time Updates

The system uses Server-Sent Events (SSE) for real-time progress:

```typescript
// Frontend subscribes to SSE stream
const eventSource = new EventSource(`/api/builder/${sessionId}/generate/stream`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'agent_start') {
    // Show agent starting
  } else if (data.type === 'agent_log') {
    // Display real-time logs
  } else if (data.type === 'agent_complete') {
    // Update agent status
  } else if (data.type === 'workflow_complete') {
    // Fetch artifacts and display
    getArtifacts(sessionId).then(artifacts => {
      setResult(artifacts);
      setCurrentStep(10); // Go to download step
    });
  }
};
```

## Verification

✅ **Backend generates artifacts** - Confirmed in `backend/agents/fiori_ui.py`, `data_modeling.py`, etc.  
✅ **Artifacts stored in state** - Confirmed in `backend/agents/state.py` (BuilderState)  
✅ **Artifacts persisted to DB** - Confirmed in `backend/api/builder.py` (session.configuration)  
✅ **API returns artifacts** - Confirmed in `GET /artifacts` endpoint  
✅ **Frontend displays artifacts** - Confirmed in `ProjectTree.tsx`, `ArtifactEditor.tsx`  
✅ **Download works** - Confirmed in `GET /download` endpoint  

## Conclusion

The artifact flow is **complete and functional**. Generated files flow seamlessly from AI agents → database → API → frontend display → user download.
