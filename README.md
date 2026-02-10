<div align="center">

# 🚀 SAP CAPM + Fiori Multi-Agent App Builder

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14+-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-FF6F00?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![SAP](https://img.shields.io/badge/SAP-CAP%20%2B%20Fiori-0FAAFF?style=for-the-badge&logo=sap&logoColor=white)](https://cap.cloud.sap)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**🤖 AI-powered platform that uses LLM-driven agents to generate production-ready SAP CAPM + SAP Fiori applications via LangGraph multi-agent orchestration**

[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[AI Agents](#-ai-agents) •
[API Reference](#-api-reference) •
[Contributing](#-contributing)

</div>

---

## ✨ Features

| Feature                       | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| 🤖 **9 LLM-Driven AI Agents** | Each agent uses LLM calls to generate real SAP CAP code   |
| 🔄 **Multi-LLM Support**      | OpenAI GPT-5.2, Google Gemini 3, DeepSeek V3.2, Kimi K2.5 |
| 🧙 **8-Step Wizard**          | Intuitive UI to configure and generate your app           |
| 📦 **Complete SAP Project**   | CDS schemas, OData services, Fiori Elements UI            |
| 🔐 **Security Configured**    | xs-security.json with roles, scopes, and auth annotations |
| 🚀 **Deployment Ready**       | mta.yaml, CI/CD pipelines, Docker configs                 |
| 🛡️ **Robust Fallbacks**       | Template-based generation as fallback if LLM fails        |
| 📚 **Auto Documentation**     | Compliance reports and extension guides generated         |

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SAP CAPM APP BUILDER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐    ┌──────────────────────┐    ┌───────────────┐ │
│  │   Frontend (Next.js) │    │  Backend (FastAPI)   │    │   Database    │ │
│  ├──────────────────────┤    ├──────────────────────┤    ├───────────────┤ │
│  │ • 8-Step Wizard      │───▶│ • REST API           │───▶│ • SQLite      │ │
│  │ • Live Preview       │    │ • Session Manager    │    │ • PostgreSQL  │ │
│  │ • Code Viewer        │◀───│ • Code Generator     │    │               │ │
│  └──────────────────────┘    └──────────┬───────────┘    └───────────────┘ │
│                                         │                                   │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      AI Engine (LangGraph)                            │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │   📝    │ │   🗃️    │ │   🌐    │ │   💼    │ │   🎨    │        │  │
│  │  │Require- │▶│  Data   │▶│ Service │▶│Business │▶│  Fiori  │        │  │
│  │  │ ments   │ │Modeling │ │Exposure │ │  Logic  │ │   UI    │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────┬────┘        │  │
│  │                                                        │             │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────▼────────┐   │  │
│  │  │   🔐    │ │   🔧    │ │   🚀    │ │           ✅             │   │  │
│  │  │Security │▶│Extension│▶│ Deploy  │▶│      Validation          │   │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                         │                                   │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         LLM Providers                                 │  │
│  ├──────────────┬───────────────┬───────────────┬───────────────────────┤  │
│  │ 🧠 OpenAI    │ 💎 Gemini     │ 🔍 DeepSeek   │ 🌙 Kimi              │  │
│  │ GPT-5.2      │ Gemini 3      │ V3.2          │ K2.5                  │  │
│  └──────────────┴───────────────┴───────────────┴───────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Workflow Pipeline

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          9-AGENT WORKFLOW PIPELINE                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1           Phase 2              Phase 3           Phase 4          │
│  ANALYSIS          DESIGN               IMPLEMENTATION    FINALIZATION     │
│                                                                             │
│  ┌─────────┐      ┌─────────┐          ┌─────────┐       ┌─────────┐      │
│  │   📝    │      │   🗃️    │          │   💼    │       │   🔧    │      │
│  │Require- │─────▶│  Data   │─────────▶│Business │──┐    │Extension│      │
│  │ ments   │      │Modeling │          │  Logic  │  │    └────┬────┘      │
│  └─────────┘      └────┬────┘          └─────────┘  │         │           │
│                        │                            │         ▼           │
│                        │               ┌─────────┐  │    ┌─────────┐      │
│                        │               │   🎨    │──┼───▶│   🚀    │      │
│                        ▼               │  Fiori  │  │    │ Deploy  │      │
│                   ┌─────────┐          │   UI    │  │    └────┬────┘      │
│                   │   🌐    │          └─────────┘  │         │           │
│                   │ Service │──────────────────────▶│         ▼           │
│                   │Exposure │          ┌─────────┐  │    ┌─────────┐      │
│                   └─────────┘          │   🔐    │──┘    │   ✅    │      │
│                                        │Security │       │Validate │      │
│                                        └─────────┘       └─────────┘      │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Generated Project Structure

```
📦 generated-sap-app/
├── 📁 db/                      # Database Layer
│   ├── schema.cds              # CDS Entity Definitions (LLM-generated)
│   ├── extensions.cds          # Extension Aspects (Clean Core)
│   └── data/                   # Sample CSV Data
│       ├── com.company-Entity1.csv
│       └── com.company-Entity2.csv
│
├── 📁 srv/                     # Service Layer
│   ├── service.cds             # Service Definition (LLM-generated)
│   ├── service.js              # Event Handlers with real business logic
│   ├── annotations.cds         # OData/Fiori Annotations
│   ├── auth.cds                # Authentication Config
│   ├── auth-annotations.cds    # Authorization Restrictions
│   └── lib/
│       ├── utils.js             # Utility Functions
│       └── hooks.js             # Extension Hook Registry
│
├── 📁 app/{entity}/webapp/     # UI Layer (Fiori Elements)
│   ├── manifest.json           # UI5 App Descriptor
│   ├── Component.js            # UI5 Component
│   ├── index.html              # Standalone Entry Point
│   └── i18n/
│       └── i18n.properties     # Translations
│
├── 📁 docs/                    # Auto-Generated Docs
│   ├── EXTENSION_GUIDE.md      # Extension Developer Guide
│   └── COMPLIANCE_REPORT.md    # Validation Results
│
├── 📁 test/data/               # Test Data
│   └── mock-users.csv          # Mock Users for Dev Testing
│
├── 📁 .github/workflows/       # CI/CD
│   └── deploy.yml              # GitHub Actions Pipeline
│
├── xs-security.json            # XSUAA Security Config
├── .cdsrc.json                 # CDS Runtime Auth Config
├── mta.yaml                    # Multi-Target App Descriptor
├── Dockerfile                  # Container Image
├── docker-compose.yml          # Local Dev Orchestration
├── package.json                # Node.js Dependencies
└── README.md                   # Generated Documentation
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Purpose                     |
| ----------- | ------- | --------------------------- |
| Python      | 3.11+   | Backend runtime             |
| Node.js     | 18+     | Frontend runtime            |
| Docker      | Latest  | Containerization (optional) |
| LLM API Key | -       | At least one provider       |

### Installation

```bash
# Clone the repository
git clone https://github.com/Nagarjundas1994-AiAgents/SAP-CAPM-APP-BUILDER.git
cd SAP-CAPM-APP-BUILDER

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

| URL                                 | Description      |
| ----------------------------------- | ---------------- |
| 🖥️ http://localhost:3000            | Landing Page     |
| 🧙 http://localhost:3000/builder    | 8-Step Wizard    |
| 📚 http://localhost:8000/api/docs   | Swagger API Docs |
| ❤️ http://localhost:8000/api/health | Health Check     |

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

All agents are **LLM-driven** — each calls the configured LLM with expert SAP system prompts and project context to generate production-quality code. If an LLM call fails, every agent falls back to robust template-based generation.

### Agent Overview

| #   | Agent                | Icon | LLM Generates                                                 |
| --- | -------------------- | ---- | ------------------------------------------------------------- |
| 1   | **Requirements**     | 📝   | Entity extraction, field inference, relationship mapping      |
| 2   | **Data Modeling**    | 🗃️   | `db/schema.cds` with types, aspects, associations             |
| 3   | **Service Exposure** | 🌐   | `srv/service.cds` + `srv/annotations.cds`                     |
| 4   | **Business Logic**   | 💼   | `srv/service.js` with validations, calculations, side effects |
| 5   | **Fiori UI**         | 🎨   | `manifest.json`, `Component.js`, `i18n`, `index.html`         |
| 6   | **Security**         | 🔐   | `xs-security.json`, auth CDS, `.cdsrc.json`, mock users       |
| 7   | **Extension**        | 🔧   | CDS aspects, hook registry, extension guide                   |
| 8   | **Deployment**       | �    | `mta.yaml`, GitHub Actions, Dockerfile, docker-compose        |
| 9   | **Validation**       | ✅   | Holistic LLM review + rule-based checks, compliance report    |

### How LLM Generation Works

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    LLM-DRIVEN AGENT PATTERN                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. SYSTEM PROMPT         Expert SAP knowledge injected per agent       │
│     ┌─────────────┐       (CDS syntax, Fiori best practices, etc.)      │
│     │  SAP Expert  │                                                    │
│     │  Knowledge   │                                                    │
│     └──────┬──────┘                                                     │
│            │                                                            │
│  2. CONTEXT ASSEMBLY      Entities, relationships, business rules,      │
│     ┌──────▼──────┐       previously generated schema/service artifacts │
│     │  Project    │                                                     │
│     │  Context    │                                                     │
│     └──────┬──────┘                                                     │
│            │                                                            │
│  3. LLM CALL              generate() via configured provider            │
│     ┌──────▼──────┐       (OpenAI / Gemini / DeepSeek / Kimi)           │
│     │    LLM      │                                                     │
│     │  Provider   │                                                     │
│     └──────┬──────┘                                                     │
│            │                                                            │
│  4. PARSE & VALIDATE      JSON parsing, sanity checks on output         │
│     ┌──────▼──────┐                                                     │
│     │   Parse +   │──── ❌ On failure ────▶ TEMPLATE FALLBACK           │
│     │  Validate   │                                                     │
│     └──────┬──────┘                                                     │
│            │ ✅                                                         │
│  5. OUTPUT                Generated file(s) added to state              │
│     ┌──────▼──────┐                                                     │
│     │  Artifacts  │                                                     │
│     └─────────────┘                                                     │
│                                                                         │
└──────────────────────────────────────────────────────────────────────────┘
```

### Agent State Machine

```
                              ┌─────────────────────────────────────┐
                              │          SESSION CREATED            │
                              └─────────────────┬───────────────────┘
                                                │
                                                ▼
                              ┌─────────────────────────────────────┐
                              │         GENERATE TRIGGERED          │
                              └─────────────────┬───────────────────┘
                                                │
        ┌───────────────────────────────────────┼───────────────────────────────────────┐
        │                                       │                                       │
        ▼                                       ▼                                       ▼
┌───────────────┐                     ┌───────────────┐                       ┌───────────────┐
│ Requirements  │────────────────────▶│ Data Modeling │──────────────────────▶│   Service     │
│    Agent      │                     │    Agent      │                       │    Agent      │
└───────────────┘                     └───────────────┘                       └───────┬───────┘
                                                                                      │
                              ┌─────────────────┬─────────────────┬─────────────────┘
                              │                 │                 │
                              ▼                 ▼                 ▼
                      ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
                      │ Business Logic│ │   Fiori UI    │ │   Security    │
                      │    Agent      │ │    Agent      │ │    Agent      │
                      └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
                              │                 │                 │
                              └─────────────────┼─────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │         Extension Agent           │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │         Deployment Agent          │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │         Validation Agent          │
                              └─────────────────┬─────────────────┘
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │                                               │
                        ▼                                               ▼
              ┌───────────────────┐                           ┌───────────────────┐
              │    ✅ COMPLETED   │                           │    ❌ FAILED      │
              └───────────────────┘                           └───────────────────┘
```

---

## 📁 Project Structure

```
sap-app-builder/
├── 📁 backend/
│   ├── 📁 agents/              # LLM-driven LangGraph agents
│   │   ├── graph.py            # Agent orchestration graph
│   │   ├── state.py            # Shared state definition
│   │   ├── llm_providers.py    # Multi-LLM support
│   │   ├── requirements.py     # Requirements analysis (LLM)
│   │   ├── data_modeling.py    # CDS schema generation (LLM + fallback)
│   │   ├── service_exposure.py # OData service (LLM + fallback)
│   │   ├── business_logic.py   # Event handlers (LLM + fallback)
│   │   ├── fiori_ui.py         # Fiori Elements (LLM + fallback)
│   │   ├── security.py         # XSUAA config (LLM + fallback)
│   │   ├── extension.py        # Clean Core (LLM + fallback)
│   │   ├── deployment.py       # MTA config (LLM + fallback)
│   │   └── validation.py       # LLM review + rule-based checks
│   ├── 📁 api/                 # FastAPI routes
│   │   ├── builder.py          # Generation endpoints
│   │   └── sessions.py         # Session management
│   ├── 📁 models/              # SQLAlchemy models
│   ├── 📁 templates/           # Jinja2 templates
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuration
│   └── database.py             # DB connection
│
├── 📁 frontend/
│   ├── 📁 src/
│   │   ├── 📁 app/
│   │   │   ├── page.tsx        # Landing page
│   │   │   └── 📁 builder/
│   │   │       └── page.tsx    # 8-Step Wizard
│   │   ├── 📁 components/
│   │   └── 📁 lib/
│   │       └── api.ts          # API client
│   └── package.json
│
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 🔌 API Reference

### Session APIs

| Method   | Endpoint             | Description           |
| -------- | -------------------- | --------------------- |
| `POST`   | `/api/sessions`      | Create new session    |
| `GET`    | `/api/sessions/{id}` | Get session details   |
| `PUT`    | `/api/sessions/{id}` | Update session config |
| `DELETE` | `/api/sessions/{id}` | Delete session        |

### Builder APIs

| Method | Endpoint                      | Description             |
| ------ | ----------------------------- | ----------------------- |
| `POST` | `/api/builder/{id}/generate`  | Start generation        |
| `GET`  | `/api/builder/{id}/status`    | Get generation status   |
| `GET`  | `/api/builder/{id}/artifacts` | Get generated artifacts |
| `GET`  | `/api/builder/{id}/download`  | Download project ZIP    |

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

| Variable               | Required | Default              | Description           |
| ---------------------- | -------- | -------------------- | --------------------- |
| `OPENAI_API_KEY`       | ⭐       | -                    | OpenAI API key        |
| `GOOGLE_API_KEY`       | ⭐       | -                    | Google Gemini API key |
| `DEEPSEEK_API_KEY`     | ⭐       | -                    | DeepSeek API key      |
| `KIMI_API_KEY`         | ⭐       | -                    | Kimi/Moonshot API key |
| `DEFAULT_LLM_PROVIDER` | ❌       | `openai`             | Default LLM provider  |
| `DEFAULT_LLM_MODEL`    | ❌       | `gpt-5.2`            | Default model         |
| `DATABASE_URL`         | ❌       | `sqlite:///./app.db` | Database connection   |
| `ENVIRONMENT`          | ❌       | `development`        | Environment mode      |

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

# Test LLM connections
python test_llm_apis.py
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

[![GitHub Stars](https://img.shields.io/github/stars/Nagarjundas1994-AiAgents/SAP-CAPM-APP-BUILDER?style=social)](https://github.com/Nagarjundas1994-AiAgents/SAP-CAPM-APP-BUILDER)

</div>
