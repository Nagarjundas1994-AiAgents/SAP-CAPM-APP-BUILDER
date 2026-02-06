"""
Unit Tests for LangGraph Agents
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agents.state import BuilderState
from backend.agents.requirements import requirements_agent
from backend.agents.data_modeling import data_modeling_agent


class TestRequirementsAgent:
    """Tests for Requirements Agent."""

    @pytest.mark.asyncio
    async def test_requirements_agent_with_domain_template(self, sample_builder_state):
        """Test requirements agent with a domain template."""
        state = BuilderState(sample_builder_state)
        
        # Mock the LLM manager
        with patch("backend.agents.requirements.get_llm_manager") as mock_llm:
            mock_manager = MagicMock()
            mock_manager.get_provider.return_value = MagicMock()
            mock_llm.return_value = mock_manager
            
            result = await requirements_agent(state)
            
            assert result["current_agent"] == "requirements"
            assert len(result["agent_history"]) > 0
            assert result["agent_history"][-1]["agent_name"] == "requirements"

    @pytest.mark.asyncio
    async def test_requirements_agent_sets_entities(self, sample_builder_state):
        """Test that requirements agent sets entities in state."""
        state = BuilderState(sample_builder_state)
        
        with patch("backend.agents.requirements.get_llm_manager") as mock_llm:
            mock_manager = MagicMock()
            mock_llm.return_value = mock_manager
            
            result = await requirements_agent(state)
            
            # Should have entities (either from template or LLM)
            assert "entities" in result


class TestDataModelingAgent:
    """Tests for Data Modeling Agent."""

    @pytest.mark.asyncio
    async def test_data_modeling_creates_schema(self, sample_builder_state):
        """Test data modeling agent creates CDS schema."""
        state = BuilderState(sample_builder_state)
        
        with patch("backend.agents.data_modeling.get_llm_manager") as mock_llm:
            mock_manager = MagicMock()
            mock_llm.return_value = mock_manager
            
            result = await data_modeling_agent(state)
            
            assert result["current_agent"] == "data_modeling"
            
            # Should have created db artifacts
            db_artifacts = [a for a in result.get("artifacts", []) 
                          if a.get("path", "").startswith("db/")]
            assert len(db_artifacts) > 0

    @pytest.mark.asyncio
    async def test_data_modeling_includes_managed_aspect(self, sample_builder_state):
        """Test that schema includes managed aspect for audit fields."""
        state = BuilderState(sample_builder_state)
        
        with patch("backend.agents.data_modeling.get_llm_manager") as mock_llm:
            mock_manager = MagicMock()
            mock_llm.return_value = mock_manager
            
            result = await data_modeling_agent(state)
            
            # Find the schema artifact
            schema = next(
                (a for a in result.get("artifacts", []) 
                 if "schema.cds" in a.get("path", "")),
                None
            )
            
            if schema:
                assert "managed" in schema.get("content", "")


class TestAgentHistory:
    """Tests for agent history tracking."""

    @pytest.mark.asyncio
    async def test_agent_records_execution_time(self, sample_builder_state):
        """Test that agents record execution duration."""
        state = BuilderState(sample_builder_state)
        
        with patch("backend.agents.requirements.get_llm_manager"):
            result = await requirements_agent(state)
            
            history = result["agent_history"][-1]
            assert "duration_ms" in history
            assert history["started_at"] is not None
            assert history["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_agent_history_accumulates(self, sample_builder_state):
        """Test that agent history accumulates across agents."""
        state = BuilderState(sample_builder_state)
        
        with patch("backend.agents.requirements.get_llm_manager"):
            with patch("backend.agents.data_modeling.get_llm_manager"):
                result1 = await requirements_agent(state)
                result2 = await data_modeling_agent(result1)
                
                assert len(result2["agent_history"]) >= 2
