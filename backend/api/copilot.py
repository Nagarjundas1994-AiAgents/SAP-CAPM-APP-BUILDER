"""
Copilot API - Perform targeted file modifications using LLMs
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.session import Session
from backend.agents.llm_providers import get_llm_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class CopilotEditRequest(BaseModel):
    """Request for targeted copilot edits."""
    path: str
    prompt: str


class CopilotEditResponse(BaseModel):
    """Response containing the modified artifact content."""
    session_id: str
    path: str
    content: str
    explanation: str
    timestamp: str


@router.post("/{session_id}/copilot/edit", response_model=CopilotEditResponse)
async def copilot_edit_artifact(
    session_id: str,
    request: CopilotEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Directly modifies a specific generated artifact based on a natural language prompt.
    """
    # 1. Fetch Session & Config
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
        
    config = session.configuration or {}
    
    # 2. Find Artifact Content
    target_artifact = None
    target_category = None
    
    for category in ["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_deployment", "artifacts_docs"]:
        artifacts = config.get(category, [])
        for art in artifacts:
            if art["path"] == request.path:
                target_artifact = art
                target_category = category
                break
        if target_artifact:
            break
            
    if not target_artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {request.path} not found"
        )

    # 3. Call LLM to modify the file
    llm = get_llm_manager()
    provider = config.get("llm_provider", "openai")
    
    system_prompt = '''You are a principal SAP software engineer pair-programming with the user.
Your task is to modify the provided source code based perfectly on the user's instructions.

CRITICAL RULES:
1. ONLY return the modified source code. 
2. NO markdown formatting blocks like ```javascript or ```cds.
3. Keep the surrounding unchanged code exactly as is.
4. Ensure the syntax remains valid after your modifications.
'''
    
    user_prompt = f'''Modify this file according to the following request:

File Path: {request.path}
User Request: {request.prompt}

Current Content:
{target_artifact["content"]}
'''

    try:
        logger.info(f"Copilot modifying {request.path} via {provider}...")
        response = await llm.generate_structured(
            provider=provider,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "modified_content": {"type": "string", "description": "The exact modified source code. No backticks."},
                    "explanation": {"type": "string", "description": "Brief explanation of what was changed."}
                },
                "required": ["modified_content", "explanation"]
            }
        )
        
        # 4. Save modifications back to DB
        modified_content = response.get("modified_content", target_artifact["content"])
        explanation = response.get("explanation", "Modification applied successfully.")
        
        target_artifact["content"] = modified_content
        session.configuration = config  # update JSON column
        session.updated_at = datetime.utcnow()
        await db.commit()
        
        return CopilotEditResponse(
            session_id=session_id,
            path=request.path,
            content=modified_content,
            explanation=explanation,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Copilot LLM edit failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Copilot edit failed: {str(e)}"
        )
