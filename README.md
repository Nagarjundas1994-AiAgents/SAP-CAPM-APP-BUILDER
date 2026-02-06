# SAP CAPM + Fiori Multi-Agent App Builder

AI-powered platform for generating production-ready SAP CAPM + SAP Fiori applications using LangGraph multi-agent orchestration.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional)

### Local Development

```bash
# Backend
pip install -e .
copy .env.example .env  # Add your API key
python -m backend.main

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

| URL                            | Description       |
| ------------------------------ | ----------------- |
| http://localhost:8000/api/docs | API Documentation |
| http://localhost:3000          | Frontend UI       |
| http://localhost:3000/builder  | 8-Step Wizard     |

### Docker

```bash
docker-compose up
```

## 🤖 AI Agents

| Agent            | Purpose                             |
| ---------------- | ----------------------------------- |
| Requirements     | Domain analysis & entity extraction |
| Data Modeling    | CDS schema generation               |
| Service Exposure | OData service definitions           |
| Business Logic   | Event handlers                      |
| Fiori UI         | Fiori Elements manifest             |
| Security         | xs-security.json & auth             |
| Extension        | Clean Core hooks                    |
| Deployment       | mta.yaml & CI/CD                    |
| Validation       | SAP compliance check                |

## 📁 Project Structure

```
├── backend/
│   ├── agents/         # 9 LangGraph agents
│   ├── api/            # FastAPI routes
│   ├── models/         # SQLAlchemy models
│   └── templates/      # Jinja2 templates
├── frontend/
│   └── src/app/        # Next.js pages
├── Dockerfile
└── docker-compose.yml
```

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest backend/tests -v
```

## 🔑 Environment Variables

| Variable               | Description           |
| ---------------------- | --------------------- |
| `OPENAI_API_KEY`       | OpenAI API key        |
| `GEMINI_API_KEY`       | Google Gemini API key |
| `DEEPSEEK_API_KEY`     | DeepSeek API key      |
| `DEFAULT_LLM_PROVIDER` | Default: `openai`     |

## 📄 License

MIT
