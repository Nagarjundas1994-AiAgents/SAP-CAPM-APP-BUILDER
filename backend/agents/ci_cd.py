"""
Agent: CI/CD

GitHub Actions pipeline, MTA build config, quality gates.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent
from backend.agents.resilience import with_timeout

logger = logging.getLogger(__name__)


CI_CD_SYSTEM_PROMPT = """You are a CI/CD and DevOps expert for SAP CAP applications.
Your task is to design comprehensive CI/CD pipelines with quality gates and deployment automation.

CI/CD PRINCIPLES:
1. Pipeline Stages: Build, Test, Security Scan, Deploy
2. Quality Gates: Lint, unit tests, integration tests, code coverage
3. Deployment Stages: Dev, Staging, Production
4. MTA Build: SAP-specific multi-target application build

OUTPUT FORMAT:
Return valid JSON:
{
  "enabled": true/false,
  "platform": "github_actions/gitlab_ci/jenkins",
  "quality_gates": ["lint", "test", "security-scan"],
  "deployment_stages": ["dev", "staging", "production"],
  "github_actions_workflow": "string (full YAML content for .github/workflows/ci.yml)"
}

Return ONLY valid JSON."""


CI_CD_PROMPT = """Design a CI/CD pipeline for this SAP CAP application.

Project: {project_name}
Description: {description}

CI/CD Enabled: {ci_cd_enabled}
Platform: {ci_cd_platform}

Tasks:
1. Define pipeline stages (build, test, deploy)
2. Configure quality gates (lint, test, security scan)
3. Set up deployment stages (dev, staging, production)
4. Generate GitHub Actions workflow YAML

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)
async def ci_cd_agent(state: BuilderState) -> dict[str, Any]:
    """
    CI/CD Agent - GitHub Actions, MTA build, quality gates.
    
    Generates:
    - GitHub Actions workflow
    - MTA build configuration
    - Quality gate definitions
    - Deployment pipeline
    """
    agent_name = "ci_cd"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting CI/CD Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "ci_cd"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting CI/CD phase...")
    
    # Check retry count
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exhausted")
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        return {
            "agent_failed": True,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": f"Max retries ({max_retries}) exhausted",
                "logs": None,
            }],
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }
    
    try:
    
        # Get context
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        ci_cd_enabled = state.get("ci_cd_enabled", False)
        ci_cd_platform = state.get("ci_cd_platform", "github_actions")
    
        if not ci_cd_enabled:
            log_progress(state, "CI/CD not enabled, skipping...")
            ci_cd_config = {"enabled": False}
            generated_files = []
        else:
            # Retrieve RAG context
            rag_docs = await retrieve_for_agent("ci_cd", f"GitHub Actions SAP CAP MTA build {project_name}")
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            prompt = CI_CD_PROMPT.format(
                project_name=project_name,
                description=description or "No description provided",
                ci_cd_enabled=ci_cd_enabled,
                ci_cd_platform=ci_cd_platform,
            )
            
            if rag_context:
                prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
            
            log_progress(state, f"Generating {ci_cd_platform} pipeline...")
            
            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=CI_CD_SYSTEM_PROMPT,
                state=state,
                required_keys=["enabled", "platform"],
                max_retries=3,
                agent_name="ci_cd",
            )
            
            if result:
                ci_cd_config = result
                workflow_content = result.get("github_actions_workflow", "")
                log_progress(state, f"✅ Configured {len(result.get('quality_gates', []))} quality gates")
            else:
                log_progress(state, "⚠️ LLM generation failed - using minimal CI/CD config")
                ci_cd_config = {
                    "enabled": True,
                    "platform": ci_cd_platform,
                    "quality_gates": ["lint", "test", "security-scan"],
                    "deployment_stages": ["dev", "staging", "production"]
                }
                workflow_content = f"""name: CI/CD Pipeline - {project_name}

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm install
      - name: Lint
        run: npm run lint
      - name: Run tests
        run: npm test
      - name: Build MTA
        run: npm run build
"""
            
            # Generate workflow file
            generated_files = [{
                "path": ".github/workflows/ci.yml",
                "content": workflow_content,
                "file_type": "yml"
            }]
        
        state["artifacts_deployment"] = state.get("artifacts_deployment", []) + generated_files
    
        state["ci_cd_config"] = ci_cd_config
        state["needs_correction"] = False
    
        # Record execution
        state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "ci_cd",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
        }]
    
        log_progress(state, "CI/CD complete.")
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
    
        return {
        "agent_history": [{
            "agent_name": agent_name,
            "status": "completed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": None,
            "logs": state.get("current_logs", []),
        }],
        "retry_counts": new_retry_counts,
        "needs_correction": False,
        "current_agent": agent_name,
        "updated_at": completed_at,
        }


    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with error: {e}")
    
    completed_at = datetime.utcnow().isoformat()
    duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
    new_retry_counts = state.get("retry_counts", {}).copy()
    new_retry_counts[agent_name] = retry_count + 1
    
    return {
        "agent_history": [{
            "agent_name": agent_name,
            "status": "failed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": str(e),
            "logs": None,
        }],
        "retry_counts": new_retry_counts,
        "needs_correction": True,
        "validation_errors": [{
            "agent": agent_name,
            "code": "AGENT_ERROR",
            "message": str(e),
            "field": None,
            "severity": "error",
        }],
        "current_agent": agent_name,
        "updated_at": completed_at,
    }