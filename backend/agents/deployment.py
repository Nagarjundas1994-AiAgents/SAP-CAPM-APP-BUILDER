"""
Agent 8: Deployment & SAP BTP Agent

Generates deployment configurations including mta.yaml, CI/CD pipelines,
Docker files, and SAP BTP service bindings.

Uses LLM to generate production-quality deployment configs with fallback to templates.
"""

import logging
import json
import re
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
    DatabaseType,
    AuthType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

DEPLOYMENT_SYSTEM_PROMPT = """You are an expert SAP BTP deployment architect.
Your task is to generate production-ready deployment configurations and essential project scaffolding files.

STRICT RULES:
1. Deployment:
   - mta.yaml (MTA 3.3+) with srv, db, and ui modules.
   - GitHub Actions for build and deploy.
   - Dockerfile (node:18-alpine) and docker-compose.yml.
2. Scaffolding:
   - package.json: Include '@sap/cds', 'express', 'passport', and SAP HANA dependencies. Add 'start' and 'watch' scripts.
   - README.md: Professional overview, setup instructions, and entity documentation.
   - .gitignore: Exclude node_modules, gen/, mta_archives/, and .env.
   - .env.example: List required environment variables (PORT, DB configuration).

OUTPUT FORMAT:
Return a JSON object:
{
  "mta_yaml": "... mta.yaml content ...",
  "github_actions": "... deploy.yml content ...",
  "dockerfile": "... Dockerfile content ...",
  "docker_compose": "... docker-compose.yml content ...",
  "package_json": "... package.json content ...",
  "readme_md": "... README.md content ...",
  "gitignore": "... .gitignore content ...",
  "env_example": "... .env.example content ..."
}
Return ONLY the JSON object."""


DEPLOYMENT_GENERATION_PROMPT = """Generate deployment configuration for this SAP CAP project.

Project Name: {project_name}
Project Namespace: {namespace}
Database Type: {database_type}
Auth Type: {auth_type}

Entities:
{entities_json}

Schema:
```
{schema_content}
```

Service:
```
{service_content}
```

Requirements:
1. mta.yaml:
   - ID: "{mta_id}"
   - Schema version "3.3.0"
   - srv module (nodejs, build with npm)
   - db-deployer module (hdb or sqlite based on db type)
   - App router / html5-deployer module  
   - Resources: xsuaa, hana/sqlite service, destination, html5-repo
   - Proper requires/provides chains between modules
   - Build parameters with before-all npm install step

2. GitHub Actions (.github/workflows/deploy.yml):
   - Node.js 18 setup
   - Install MTA build tool
   - Run `mbt build`
   - Deploy with `cf deploy`
   - Environment variables for CF API, org, space
   
3. Dockerfile:
   - Multi-stage build
   - node:18-alpine base
   - Copy package*.json, install deps, copy source
   - Expose port 4004
   - CMD ["npx", "cds", "run"]

4. docker-compose.yml:
   - App service with build context
   - Database service (postgres for dev)
   - Volume mounts for persistence
   - Environment variables

Respond with ONLY valid JSON."""


# =============================================================================
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


def _parse_llm_response(response_text: str) -> dict | None:
    try:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None


# =============================================================================
# Template Fallback Functions
# =============================================================================

def generate_mta_yaml(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    mta_id = project_name.lower().replace(" ", "-").replace("_", "-")
    db_type = state.get("database_type", DatabaseType.SQLITE.value)
    
    hana_service = "hana" if db_type == DatabaseType.HANA.value else "sqlite"
    
    mta = f"""_schema-version: '3.3.0'
ID: {mta_id}
version: 1.0.0
description: {project_name} - SAP CAP Application

parameters:
  enable-parallel-deployments: true

build-parameters:
  before-all:
    - builder: custom
      commands:
        - npm ci
        - npx cds build --production

modules:
  - name: {mta_id}-srv
    type: nodejs
    path: gen/srv
    parameters:
      buildpack: nodejs_buildpack
      memory: 256M
      disk-quota: 512M
    build-parameters:
      builder: npm
    provides:
      - name: srv-api
        properties:
          srv-url: ${{default-url}}
    requires:
      - name: {mta_id}-auth
      - name: {mta_id}-db

  - name: {mta_id}-db-deployer
    type: hdb
    path: gen/db
    parameters:
      buildpack: nodejs_buildpack
      memory: 256M
    requires:
      - name: {mta_id}-db

resources:
  - name: {mta_id}-auth
    type: org.cloudfoundry.managed-service
    parameters:
      service: xsuaa
      service-plan: application
      path: ./xs-security.json

  - name: {mta_id}-db
    type: com.sap.xs.hdi-container
    parameters:
      service: {hana_service}
      service-plan: hdi-shared
"""
    return mta


def generate_github_actions(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    return f"""name: Deploy {project_name}

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Install MTA Build Tool
        run: npm install -g mbt
      
      - name: Build MTA
        run: mbt build
      
      - name: Deploy to Cloud Foundry
        env:
          CF_API: ${{{{ secrets.CF_API }}}}
          CF_ORG: ${{{{ secrets.CF_ORG }}}}
          CF_SPACE: ${{{{ secrets.CF_SPACE }}}}
          CF_USER: ${{{{ secrets.CF_USER }}}}
          CF_PASSWORD: ${{{{ secrets.CF_PASSWORD }}}}
        run: |
          npm install -g cf-cli
          cf api $CF_API
          cf auth $CF_USER $CF_PASSWORD
          cf target -o $CF_ORG -s $CF_SPACE
          cf deploy mta_archives/*.mtar
"""


def generate_dockerfile(state: BuilderState) -> str:
    return """# Multi-stage build for SAP CAP application
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app .
EXPOSE 4004
ENV NODE_ENV=production
CMD ["npx", "cds", "run", "--in-memory"]
"""


def generate_docker_compose(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    service_name = project_name.lower().replace(" ", "-")
    return f"""version: '3.8'

services:
  {service_name}-app:
    build: .
    ports:
      - "4004:4004"
    environment:
      - NODE_ENV=development
      - CDS_REQUIRES_DB_KIND=sqlite
    volumes:
      - ./db:/app/db
      - ./srv:/app/srv
    restart: unless-stopped

  {service_name}-db:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: {service_name}
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
"""


# =============================================================================
# Main Agent Function
# =============================================================================

async def deployment_agent(state: BuilderState) -> BuilderState:
    """
    Deployment & SAP BTP Agent (LLM-Driven)
    
    Uses LLM to generate production-quality deployment configurations.
    Falls back to template-based generation if LLM fails.
    """
    logger.info("Starting Deployment Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "deployment"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting deployment configuration generation...")
    
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    database_type = state.get("database_type", DatabaseType.SQLITE.value)
    auth_type = state.get("auth_type", AuthType.XSUAA.value)
    entities = state.get("entities", [])
    provider = state.get("llm_provider")
    mta_id = project_name.lower().replace(" ", "-").replace("_", "-")
    
    schema_content = ""
    service_content = ""
    for artifact in state.get("artifacts_db", []):
        if artifact.get("path") == "db/schema.cds":
            schema_content = artifact.get("content", "")
    for artifact in state.get("artifacts_srv", []):
        if artifact.get("path") == "srv/service.cds":
            service_content = artifact.get("content", "")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven generation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        prompt = DEPLOYMENT_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            database_type=database_type,
            auth_type=auth_type,
            entities_json=json.dumps(entities, indent=2),
            schema_content=schema_content or "(not available)",
            service_content=service_content or "(not available)",
            mta_id=mta_id,
        )
        
        log_progress(state, "Calling LLM for deployment config generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=DEPLOYMENT_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("mta_yaml"):
            generated_files.append({"path": "mta.yaml", "content": parsed["mta_yaml"], "file_type": "yaml"})
            
            if parsed.get("github_actions"):
                generated_files.append({"path": ".github/workflows/deploy.yml", "content": parsed["github_actions"], "file_type": "yaml"})
            if parsed.get("dockerfile"):
                generated_files.append({"path": "Dockerfile", "content": parsed["dockerfile"], "file_type": "dockerfile"})
            if parsed.get("docker_compose"):
                generated_files.append({"path": "docker-compose.yml", "content": parsed["docker_compose"], "file_type": "yaml"})
            
            # Scaffolding
            if parsed.get("package_json"):
                generated_files.append({"path": "package.json", "content": parsed["package_json"], "file_type": "json"})
            if parsed.get("readme_md"):
                generated_files.append({"path": "README.md", "content": parsed["readme_md"], "file_type": "markdown"})
            if parsed.get("gitignore"):
                generated_files.append({"path": ".gitignore", "content": parsed["gitignore"], "file_type": "text"})
            if parsed.get("env_example"):
                generated_files.append({"path": ".env.example", "content": parsed["env_example"], "file_type": "text"})
            
            log_progress(state, "LLM-generated deployment and scaffolding files accepted.")
            llm_success = True
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for deployment: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        log_progress(state, "Generating deployment config via template fallback...")
        try:
            generated_files.append({"path": "mta.yaml", "content": generate_mta_yaml(state), "file_type": "yaml"})
            generated_files.append({"path": ".github/workflows/deploy.yml", "content": generate_github_actions(state), "file_type": "yaml"})
            generated_files.append({"path": "Dockerfile", "content": generate_dockerfile(state), "file_type": "dockerfile"})
            generated_files.append({"path": "docker-compose.yml", "content": generate_docker_compose(state), "file_type": "yaml"})
        except Exception as e:
            logger.error(f"Template fallback failed for deployment: {e}")
            errors.append({"agent": "deployment", "code": "DEPLOYMENT_ERROR", "message": f"Deployment config failed: {str(e)}", "field": None, "severity": "error"})
    
    # ==========================================================================
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    # Get retry configuration
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("deployment", 0)
    
    # Validate critical deployment files (package.json and mta.yaml)
    critical_files = ["package.json", "mta.yaml"]
    validation_failed = False
    
    if llm_success:
        for file_path in critical_files:
            artifact = next((f for f in generated_files if f["path"] == file_path), None)
            if artifact:
                validation_results = validate_artifact(artifact["path"], artifact["content"])
                if any(result.has_errors for result in validation_results):
                    validation_failed = True
                    log_progress(state, f"Validation failed for {file_path}")
                    
                    if should_retry_agent(validation_results, retry_count, max_retries):
                        log_progress(state, f"Attempting correction (retry {retry_count + 1}/{max_retries})...")
                        
                        if "retry_counts" not in state:
                            state["retry_counts"] = {}
                        state["retry_counts"]["deployment"] = retry_count + 1
                        state["needs_correction"] = True
                        
                        if "correction_history" not in state:
                            state["correction_history"] = []
                        state["correction_history"].append({
                            "agent": "deployment",
                            "retry": retry_count + 1,
                            "errors_found": sum(r.error_count for r in validation_results),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        state["artifacts_deployment"] = []
                        return state
                    else:
                        log_progress(state, f"⚠️ Max retries reached for {file_path}. Errors remain.")
        
        if not validation_failed:
            if retry_count > 0:
                log_progress(state, f"✅ Validation passed after {retry_count} correction(s)")
                summary = format_correction_summary("deployment", retry_count, retry_count, retry_count)
                if "auto_fixed_errors" not in state:
                    state["auto_fixed_errors"] = []
                state["auto_fixed_errors"].append({
                    "agent": "deployment",
                    "summary": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                log_progress(state, "✅ Validation passed on first attempt")

    state["needs_correction"] = False
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_deployment"] = state.get("artifacts_deployment", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "deployment",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "retry_count": retry_count,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Deployment configuration complete ({generation_method}).")
    logger.info(f"Deployment Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
