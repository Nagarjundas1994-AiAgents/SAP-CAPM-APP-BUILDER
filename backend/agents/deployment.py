"""
Agent 8: Deployment & SAP BTP Agent

Generates deployment configurations including mta.yaml, CI/CD pipelines,
Docker files, and SAP BTP service bindings.
"""

import logging
import json
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
    DeploymentTarget,
    CICDPlatform,
    DatabaseType,
    AuthType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MTA Descriptor Generation
# =============================================================================

def generate_mta_yaml(state: BuilderState) -> str:
    """Generate mta.yaml for SAP BTP deployment."""
    project_name = state.get("project_name", "app")
    project_description = state.get("project_description", "")
    database_type = state.get("database_type", DatabaseType.HANA.value)
    auth_type = state.get("auth_type", AuthType.XSUAA.value)
    fiori_main_entity = state.get("fiori_main_entity", "")
    multitenancy = state.get("multitenancy_enabled", False)
    
    # Sanitize project name for MTA
    mta_id = project_name.lower().replace(" ", "-").replace("_", "-")
    app_name = fiori_main_entity.lower() if fiori_main_entity else "app"
    
    lines = []
    lines.append(f"_schema-version: '3.2'")
    lines.append(f"ID: {mta_id}")
    lines.append(f"version: 1.0.0")
    lines.append(f"description: \"{project_description or project_name}\"")
    lines.append("")
    lines.append("parameters:")
    lines.append("  enable-parallel-deployments: true")
    lines.append("")
    lines.append("build-parameters:")
    lines.append("  before-all:")
    lines.append("    - builder: custom")
    lines.append("      commands:")
    lines.append("        - npm ci")
    lines.append("        - npx cds build --production")
    lines.append("")
    lines.append("modules:")
    lines.append("")
    
    # CAP Server Module
    lines.append(f"  - name: {mta_id}-srv")
    lines.append("    type: nodejs")
    lines.append("    path: gen/srv")
    lines.append("    parameters:")
    lines.append("      buildpack: nodejs_buildpack")
    lines.append("      memory: 256M")
    lines.append("      disk-quota: 1024M")
    lines.append("    build-parameters:")
    lines.append("      builder: npm")
    lines.append("    provides:")
    lines.append("      - name: srv-api")
    lines.append("        properties:")
    lines.append(f"          srv-url: ${{default-url}}")
    lines.append("    requires:")
    
    # Database binding
    if database_type == DatabaseType.HANA.value:
        lines.append(f"      - name: {mta_id}-db")
    
    # Auth binding
    if auth_type != AuthType.MOCK.value:
        lines.append(f"      - name: {mta_id}-auth")
    
    lines.append("")
    
    # Database Deployer Module (HANA only)
    if database_type == DatabaseType.HANA.value:
        lines.append(f"  - name: {mta_id}-db-deployer")
        lines.append("    type: hdb")
        lines.append("    path: gen/db")
        lines.append("    parameters:")
        lines.append("      buildpack: nodejs_buildpack")
        lines.append("    requires:")
        lines.append(f"      - name: {mta_id}-db")
        lines.append("")
    
    # App Router Module
    lines.append(f"  - name: {mta_id}-app-router")
    lines.append("    type: approuter.nodejs")
    lines.append(f"    path: app/{app_name}")
    lines.append("    parameters:")
    lines.append("      memory: 256M")
    lines.append("      disk-quota: 256M")
    lines.append("    requires:")
    lines.append("      - name: srv-api")
    lines.append("        group: destinations")
    lines.append("        properties:")
    lines.append(f"          name: {mta_id}-srv")
    lines.append("          url: ~{srv-url}")
    lines.append("          forwardAuthToken: true")
    
    if auth_type != AuthType.MOCK.value:
        lines.append(f"      - name: {mta_id}-auth")
    
    lines.append("")
    lines.append("resources:")
    lines.append("")
    
    # HANA Service
    if database_type == DatabaseType.HANA.value:
        lines.append(f"  - name: {mta_id}-db")
        lines.append("    type: com.sap.xs.hdi-container")
        lines.append("    parameters:")
        lines.append("      service: hana")
        lines.append("      service-plan: hdi-shared")
        lines.append("")
    
    # XSUAA Service
    if auth_type != AuthType.MOCK.value:
        lines.append(f"  - name: {mta_id}-auth")
        lines.append("    type: org.cloudfoundry.managed-service")
        lines.append("    parameters:")
        lines.append("      service: xsuaa")
        lines.append("      service-plan: application")
        lines.append("      path: ./xs-security.json")
        lines.append("      config:")
        lines.append(f"        xsappname: {mta_id}-${{org}}-${{space}}")
        lines.append("        tenant-mode: dedicated")
    
    return "\n".join(lines)


def generate_github_actions(state: BuilderState) -> str:
    """Generate GitHub Actions CI/CD pipeline."""
    project_name = state.get("project_name", "app")
    mta_id = project_name.lower().replace(" ", "-").replace("_", "-")
    
    return f"""name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  MTA_ID: {mta_id}

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm test

      - name: Build MTA
        run: |
          npm install -g mbt
          mbt build -t ./mta_archives

      - name: Upload MTA archive
        uses: actions/upload-artifact@v4
        with:
          name: mta-archive
          path: mta_archives/*.mtar

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - name: Download MTA archive
        uses: actions/download-artifact@v4
        with:
          name: mta-archive
          path: mta_archives

      - name: Deploy to SAP BTP
        env:
          CF_API: ${{{{ secrets.CF_API }}}}
          CF_ORG: ${{{{ secrets.CF_ORG }}}}
          CF_SPACE: ${{{{ secrets.CF_SPACE }}}}
          CF_USER: ${{{{ secrets.CF_USER }}}}
          CF_PASSWORD: ${{{{ secrets.CF_PASSWORD }}}}
        run: |
          wget -q -O cf-cli.tgz "https://packages.cloudfoundry.org/stable?release=linux64-binary&version=v8&source=github"
          tar -xzf cf-cli.tgz
          ./cf login -a $CF_API -u $CF_USER -p $CF_PASSWORD -o $CF_ORG -s $CF_SPACE
          ./cf deploy mta_archives/*.mtar -f
"""


def generate_dockerfile(state: BuilderState) -> str:
    """Generate Dockerfile for containerized deployment."""
    return """# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source
COPY . .

# Build CDS
RUN npx cds build --production

# Production stage
FROM node:20-alpine

WORKDIR /app

# Copy built files
COPY --from=builder /app/gen ./gen
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

# Set environment
ENV NODE_ENV=production
ENV PORT=4004

EXPOSE 4004

# Start server
CMD ["npm", "start"]
"""


def generate_docker_compose(state: BuilderState) -> str:
    """Generate docker-compose.yml for local development."""
    project_name = state.get("project_name", "app")
    mta_id = project_name.lower().replace(" ", "-").replace("_", "-")
    
    return f"""version: '3.8'

services:
  {mta_id}-srv:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "4004:4004"
    environment:
      - NODE_ENV=development
      - cds_requires_db_kind=sqlite
    volumes:
      - .:/app
      - /app/node_modules
    command: npx cds watch

  # Optional: Add HANA Express for local HANA testing
  # hana-express:
  #   image: saplabs/hanaexpress:2.00.054.00.20210603.1
  #   hostname: hxe
  #   ports:
  #     - "39017:39017"
  #     - "39041:39041"
  #   environment:
  #     - AGREE_TO_SAP_LICENSE=Y
  #     - MASTER_PASSWORD=HXEHana1
"""


# =============================================================================
# Main Agent Function
# =============================================================================

async def deployment_agent(state: BuilderState) -> BuilderState:
    """
    Deployment & SAP BTP Agent
    
    Generates:
    1. mta.yaml - MTA deployment descriptor
    2. .github/workflows/deploy.yml - CI/CD pipeline
    3. Dockerfile - Container image
    4. docker-compose.yml - Local orchestration
    
    Returns updated state with deployment configuration files.
    """
    logger.info("Starting Deployment Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "deployment"
    state["updated_at"] = now
    
    deployment_target = state.get("deployment_target", DeploymentTarget.CF.value)
    ci_cd_enabled = state.get("ci_cd_enabled", True)
    ci_cd_platform = state.get("ci_cd_platform", CICDPlatform.GITHUB_ACTIONS.value)
    docker_enabled = state.get("docker_enabled", True)
    
    # ==========================================================================
    # Generate mta.yaml
    # ==========================================================================
    if deployment_target in [DeploymentTarget.CF.value, DeploymentTarget.KYMA.value]:
        try:
            mta = generate_mta_yaml(state)
            generated_files.append({
                "path": "mta.yaml",
                "content": mta,
                "file_type": "yaml",
            })
            logger.info("Generated mta.yaml")
        except Exception as e:
            logger.error(f"Failed to generate mta.yaml: {e}")
            errors.append({
                "agent": "deployment",
                "code": "MTA_GENERATION_ERROR",
                "message": f"Failed to generate mta.yaml: {str(e)}",
                "field": None,
                "severity": "error",
            })
    
    # ==========================================================================
    # Generate CI/CD Pipeline
    # ==========================================================================
    if ci_cd_enabled:
        try:
            if ci_cd_platform == CICDPlatform.GITHUB_ACTIONS.value:
                pipeline = generate_github_actions(state)
                generated_files.append({
                    "path": ".github/workflows/deploy.yml",
                    "content": pipeline,
                    "file_type": "yaml",
                })
                logger.info("Generated .github/workflows/deploy.yml")
        except Exception as e:
            logger.error(f"Failed to generate CI/CD pipeline: {e}")
    
    # ==========================================================================
    # Generate Docker files
    # ==========================================================================
    if docker_enabled:
        try:
            dockerfile = generate_dockerfile(state)
            generated_files.append({
                "path": "Dockerfile",
                "content": dockerfile,
                "file_type": "dockerfile",
            })
            
            docker_compose = generate_docker_compose(state)
            generated_files.append({
                "path": "docker-compose.yml",
                "content": docker_compose,
                "file_type": "yaml",
            })
            logger.info("Generated Docker files")
        except Exception as e:
            logger.error(f"Failed to generate Docker files: {e}")
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_deployment"] = state.get("artifacts_deployment", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "deployment",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Deployment Agent completed. Generated {len(generated_files)} files.")
    
    return state
