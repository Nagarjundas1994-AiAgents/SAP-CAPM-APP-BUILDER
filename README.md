<![CDATA[<div align="center">

# 🚀 SAP CAPM + Fiori Multi-Agent App Builder

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14+-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-FF6F00?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![SAP](https://img.shields.io/badge/SAP-CAP%20%2B%20Fiori-0FAAFF?style=for-the-badge&logo=sap&logoColor=white)](https://cap.cloud.sap)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**🤖 AI-powered platform for generating production-ready SAP CAPM + SAP Fiori applications using LangGraph multi-agent orchestration**

[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[AI Agents](#-ai-agents) •
[API Reference](#-api-reference) •
[Contributing](#-contributing)

---

</div>

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **9 Specialized AI Agents** | Each agent handles a specific aspect of SAP development |
| 🔄 **Multi-LLM Support** | OpenAI GPT-5.2, Google Gemini 3, DeepSeek V3.2, Kimi K2.5 |
| 🧙 **8-Step Wizard** | Intuitive UI to configure and generate your app |
| 📦 **Complete SAP Project** | CDS schemas, OData services, Fiori Elements UI |
| 🔐 **Security Configured** | xs-security.json with roles and scopes |
| 🚀 **Deployment Ready** | mta.yaml for SAP BTP deployment |
| 📚 **Auto Documentation** | README and developer guides generated |

---

## 🏗️ Architecture

### System Overview

```mermaid
graph TB
    subgraph "Frontend - Next.js 14"
        UI[🖥️ Web UI]
        Wizard[🧙 8-Step Wizard]
        Preview[👁️ Live Preview]
    end

    subgraph "Backend - FastAPI"
        API[🔌 REST API]
        Sessions[📋 Session Manager]
        Generator[⚙️ Code Generator]
    end

    subgraph "AI Engine - LangGraph"
        Orchestrator[🎯 Agent Orchestrator]
        State[📊 Shared State]
        
        subgraph "Specialized Agents"
            A1[📝 Requirements]
            A2[🗃️ Data Modeling]
            A3[🌐 Service Exposure]
            A4[💼 Business Logic]
            A5[🎨 Fiori UI]
            A6[🔐 Security]
            A7[🔧 Extension]
            A8[🚀 Deployment]
            A9[✅ Validation]
        end
    end

    subgraph "LLM Providers"
        OpenAI[🧠 OpenAI GPT-5.2]
        Gemini[💎 Google Gemini 3]
        DeepSeek[🔍 DeepSeek V3.2]
        Kimi[🌙 Kimi K2.5]
    end

    subgraph "Storage"
        DB[(🗄️ SQLite/PostgreSQL)]
        Templates[📁 Jinja2 Templates]
    end

    UI --> API
    Wizard --> API
    API --> Sessions
    API --> Generator
    Generator --> Orchestrator
    Orchestrator --> State
    State --> A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 & A9
    A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 & A9 --> OpenAI & Gemini & DeepSeek & Kimi
    Sessions --> DB
    Generator --> Templates

    style UI fill:#0070f3,color:#fff
    style Wizard fill:#0070f3,color:#fff
    style API fill:#009688,color:#fff
    style Orchestrator fill:#ff6f00,color:#fff
    style OpenAI fill:#10a37f,color:#fff
    style Gemini fill:#4285f4,color:#fff
```

### Agent Workflow Pipeline

```mermaid
flowchart LR
    subgraph "Phase 1: Analysis"
        REQ[📝 Requirements<br/>Agent]
    end

    subgraph "Phase 2: Design"
        DM[🗃️ Data Modeling<br/>Agent]
        SE[🌐 Service<br/>Agent]
    end

    subgraph "Phase 3: Implementation"
        BL[💼 Business Logic<br/>Agent]
        FUI[🎨 Fiori UI<br/>Agent]
        SEC[🔐 Security<br/>Agent]
    end

    subgraph "Phase 4: Extension"
        EXT[🔧 Extension<br/>Agent]
    end

    subgraph "Phase 5: Deployment"
        DEP[🚀 Deployment<br/>Agent]
    end

    subgraph "Phase 6: Validation"
        VAL[✅ Validation<br/>Agent]
    end

    REQ --> DM
    DM --> SE
    SE --> BL & FUI & SEC
    BL & FUI & SEC --> EXT
    EXT --> DEP
    DEP --> VAL

    style REQ fill:#e3f2fd,stroke:#1976d2
    style DM fill:#e8f5e9,stroke:#388e3c
    style SE fill:#e8f5e9,stroke:#388e3c
    style BL fill:#fff3e0,stroke:#f57c00
    style FUI fill:#fff3e0,stroke:#f57c00
    style SEC fill:#fff3e0,stroke:#f57c00
    style EXT fill:#f3e5f5,stroke:#7b1fa2
    style DEP fill:#e0f7fa,stroke:#0097a7
    style VAL fill:#ffebee,stroke:#c62828
```

### Generated SAP Project Structure

```mermaid
graph TD
    subgraph "Generated SAP CAPM Project"
        ROOT[📦 my-sap-app]
        
        subgraph "Database Layer"
            DB_DIR[📁 db/]
            SCHEMA[schema.cds]
            DATA[data/]
        end

        subgraph "Service Layer"
            SRV_DIR[📁 srv/]
            SERVICE[service.cds]
            HANDLER[service.js]
            ANNOTATIONS[annotations.cds]
        end

        subgraph "UI Layer"
            APP_DIR[📁 app/]
            MANIFEST[manifest.json]
            I18N[i18n/]
            WEBAPP[webapp/]
        end

        subgraph "Deployment"
            MTA[mta.yaml]
            XSSEC[xs-security.json]
            PACKAGE[package.json]
        end

        subgraph "Documentation"
            README_GEN[README.md]
            API_DOC[API.md]
        end
    end

    ROOT --> DB_DIR & SRV_DIR & APP_DIR & MTA & README_GEN
    DB_DIR --> SCHEMA & DATA
    SRV_DIR --> SERVICE & HANDLER & ANNOTATIONS
    APP_DIR --> MANIFEST & I18N & WEBAPP
    MTA --> XSSEC & PACKAGE

    style ROOT fill:#0faaff,color:#fff
    style DB_DIR fill:#4caf50,color:#fff
    style SRV_DIR fill:#2196f3,color:#fff
    style APP_DIR fill:#9c27b0,color:#fff
```

### Data Flow Sequence

```mermaid
sequenceDiagram
    autonumber
    participant User as 👤 User
    participant UI as 🖥️ Next.js UI
    participant API as 🔌 FastAPI
    participant Orch as 🎯 Orchestrator
    participant Agents as 🤖 AI Agents
    participant LLM as 🧠 LLM Provider
    participant DB as 🗄️ Database

    User->>UI: Start Wizard
    UI->>API: POST /api/sessions
    API->>DB: Create Session
    DB-->>API: Session ID
    API-->>UI: Session Created

    User->>UI: Configure Project
    UI->>API: PUT /api/sessions/{id}
    API->>DB: Update Config
    
    User->>UI: Generate App
    UI->>API: POST /api/builder/{id}/generate
    API->>Orch: Start Generation
    
    loop For Each Agent
        Orch->>Agents: Execute Agent
        Agents->>LLM: Generate Content
        LLM-->>Agents: AI Response
        Agents->>Orch: Update State
    end
    
    Orch-->>API: Generation Complete
    API->>DB: Store Artifacts
    API-->>UI: Return Artifacts
    
    User->>UI: Download ZIP
    UI->>API: GET /api/builder/{id}/download
    API-->>User: 📦 SAP Project ZIP
```

### Technology Stack

```mermaid
mindmap
  root((SAP App Builder))
    Frontend
      Next.js 14
      TypeScript
      Tailwind CSS
      Lucide Icons
    Backend
      FastAPI
      SQLAlchemy
      Pydantic
      Jinja2
    AI Engine
      LangGraph
      LangChain
      Multi-Agent
    LLM Providers
      OpenAI GPT-5.2
      Google Gemini 3
      DeepSeek V3.2
      Kimi K2.5
    SAP Technologies
      CAP CDS
      OData V4
      Fiori Elements
      SAP BTP
    DevOps
      Docker
      GitHub Actions
      pytest
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| Docker | Latest | Containerization (optional) |
| LLM API Key | - | At least one provider |

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/sap-app-builder.git
cd sap-app-builder

# Backend setup
pip install -e .
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# Add your API keys to .env
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AI...

# Start backend
python -m backend.main

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Access Points

| URL | Description |
|-----|-------------|
| 🖥️ http://localhost:3000 | Landing Page |
| 🧙 http://localhost:3000/builder | 8-Step Wizard |
| 📚 http://localhost:8000/api/docs | Swagger API Docs |
| ❤️ http://localhost:8000/api/health | Health Check |

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## 🤖 AI Agents

### Agent Overview

| # | Agent | Icon | Purpose | Output |
|---|-------|------|---------|--------|
| 1 | **Requirements** | 📝 | Analyze domain & extract entities | Entity list, relationships |
| 2 | **Data Modeling** | 🗃️ | Generate CDS schemas | `db/schema.cds` |
| 3 | **Service Exposure** | 🌐 | Create OData services | `srv/service.cds` |
| 4 | **Business Logic** | 💼 | Write event handlers | `srv/service.js` |
| 5 | **Fiori UI** | 🎨 | Build Fiori Elements | `app/manifest.json` |
| 6 | **Security** | 🔐 | Configure authorization | `xs-security.json` |
| 7 | **Extension** | 🔧 | Add Clean Core hooks | Extension points |
| 8 | **Deployment** | 🚀 | Create deployment config | `mta.yaml` |
| 9 | **Validation** | ✅ | SAP compliance check | Validation report |

### Agent State Machine

```mermaid
stateDiagram-v2
    [*] --> Pending: Session Created
    Pending --> Running: Generate Triggered
    
    Running --> RequirementsAgent
    RequirementsAgent --> DataModelingAgent: Entities Extracted
    DataModelingAgent --> ServiceAgent: Schema Generated
    ServiceAgent --> BusinessLogicAgent: Service Defined
    ServiceAgent --> FioriUIAgent: Service Defined
    ServiceAgent --> SecurityAgent: Service Defined
    
    BusinessLogicAgent --> ExtensionAgent: Handlers Created
    FioriUIAgent --> ExtensionAgent: UI Generated
    SecurityAgent --> ExtensionAgent: Security Configured
    
    ExtensionAgent --> DeploymentAgent: Extensions Added
    DeploymentAgent --> ValidationAgent: Deploy Config Ready
    
    ValidationAgent --> Completed: All Checks Pass
    ValidationAgent --> Failed: Validation Errors
    
    Completed --> [*]
    Failed --> [*]
```

---

## 📁 Project Structure

```
sap-app-builder/
├── 📁 backend/
│   ├── 📁 agents/           # LangGraph agents
│   │   ├── graph.py         # Agent orchestration graph
│   │   ├── state.py         # Shared state definition
│   │   ├── requirements.py  # Requirements analysis
│   │   ├── data_modeling.py # CDS schema generation
│   │   ├── service_exposure.py
│   │   ├── business_logic.py
│   │   ├── fiori_ui.py
│   │   ├── security.py
│   │   ├── extension.py
│   │   ├── deployment.py
│   │   └── validation.py
│   ├── 📁 api/              # FastAPI routes
│   │   ├── builder.py       # Generation endpoints
│   │   └── sessions.py      # Session management
│   ├── 📁 models/           # SQLAlchemy models
│   │   ├── session.py
│   │   ├── artifact.py
│   │   └── user.py
│   ├── 📁 templates/        # Jinja2 templates
│   │   └── 📁 jinja_templates/
│   │       ├── 📁 cds/      # CDS templates
│   │       ├── 📁 fiori/    # Fiori templates
│   │       ├── 📁 deployment/
│   │       └── 📁 security/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   └── database.py          # DB connection
├── 📁 frontend/
│   ├── 📁 src/
│   │   ├── 📁 app/
│   │   │   ├── page.tsx     # Landing page
│   │   │   └── 📁 builder/
│   │   │       └── page.tsx # Wizard
│   │   ├── 📁 components/
│   │   │   ├── WizardLayout.tsx
│   │   │   └── AgentProgress.tsx
│   │   └── 📁 lib/
│   │       └── api.ts       # API client
│   ├── package.json
│   └── tailwind.config.js
├── 📁 tests/
│   ├── conftest.py
│   └── test_agents.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 🔌 API Reference

### Endpoints

```mermaid
graph LR
    subgraph "Session APIs"
        POST_S[POST /api/sessions] --> CREATE[Create Session]
        GET_S[GET /api/sessions/:id] --> READ[Get Session]
        PUT_S[PUT /api/sessions/:id] --> UPDATE[Update Session]
    end

    subgraph "Builder APIs"
        POST_G[POST /api/builder/:id/generate] --> GEN[Start Generation]
        GET_ST[GET /api/builder/:id/status] --> STATUS[Get Status]
        GET_A[GET /api/builder/:id/artifacts] --> ARTIFACTS[Get Artifacts]
        GET_D[GET /api/builder/:id/download] --> DOWNLOAD[Download ZIP]
    end

    subgraph "System APIs"
        GET_H[GET /api/health] --> HEALTH[Health Check]
    end
```

### Quick Examples

```bash
# Create session
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"project_name": "My SAP App"}'

# Start generation
curl -X POST http://localhost:8000/api/builder/{session_id}/generate \
  -H "Content-Type: application/json" \
  -d '{"llm_provider": "openai", "llm_model": "gpt-5.2"}'

# Download project
curl -O http://localhost:8000/api/builder/{session_id}/download
```

---

## 🔑 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ⭐ | - | OpenAI API key |
| `GOOGLE_API_KEY` | ⭐ | - | Google Gemini API key |
| `DEEPSEEK_API_KEY` | ⭐ | - | DeepSeek API key |
| `KIMI_API_KEY` | ⭐ | - | Kimi/Moonshot API key |
| `DEFAULT_LLM_PROVIDER` | ❌ | `openai` | Default LLM provider |
| `DEFAULT_LLM_MODEL` | ❌ | `gpt-5.2` | Default model |
| `DATABASE_URL` | ❌ | `sqlite:///./app.db` | Database connection |
| `ENVIRONMENT` | ❌ | `development` | Environment mode |

> ⭐ At least one LLM API key is required

---

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest backend/tests -v

# Run with coverage
pytest backend/tests --cov=backend --cov-report=html

# Run specific test
pytest backend/tests/test_agents.py -v
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Made with ❤️ for SAP Developers**

[![GitHub Stars](https://img.shields.io/github/stars/your-org/sap-app-builder?style=social)](https://github.com/your-org/sap-app-builder)

</div>
]]>
