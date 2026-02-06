"""
Integration Tests for FastAPI API Endpoints
"""

import pytest
from fastapi import status


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        response = client.get("/api/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "llm_providers" in data

    def test_health_returns_app_name(self, client):
        """Test health check includes app name."""
        response = client.get("/api/health")
        
        data = response.json()
        assert "app" in data


class TestSessionsAPI:
    """Tests for sessions API endpoints."""

    def test_create_session(self, client, sample_session_data):
        """Test creating a new session."""
        response = client.post("/api/sessions", json=sample_session_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["project_name"] == sample_session_data["project_name"]
        assert "id" in data

    def test_create_session_missing_name(self, client):
        """Test creating session without required field."""
        response = client.post("/api/sessions", json={})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_session(self, client, sample_session_data):
        """Test getting a session by ID."""
        # Create session first
        create_response = client.post("/api/sessions", json=sample_session_data)
        session_id = create_response.json()["id"]
        
        # Get session
        response = client.get(f"/api/sessions/{session_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == session_id

    def test_get_nonexistent_session(self, client):
        """Test getting a session that doesn't exist."""
        response = client.get("/api/sessions/nonexistent-id-12345")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_sessions(self, client, sample_session_data):
        """Test listing all sessions."""
        # Create a session
        client.post("/api/sessions", json=sample_session_data)
        
        response = client.get("/api/sessions")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_update_session(self, client, sample_session_data):
        """Test updating a session."""
        # Create session
        create_response = client.post("/api/sessions", json=sample_session_data)
        session_id = create_response.json()["id"]
        
        # Update session
        update_data = {"project_name": "Updated Name"}
        response = client.put(f"/api/sessions/{session_id}", json=update_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_name"] == "Updated Name"

    def test_delete_session(self, client, sample_session_data):
        """Test deleting a session."""
        # Create session
        create_response = client.post("/api/sessions", json=sample_session_data)
        session_id = create_response.json()["id"]
        
        # Delete session
        response = client.delete(f"/api/sessions/{session_id}")
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deleted
        get_response = client.get(f"/api/sessions/{session_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


class TestBuilderAPI:
    """Tests for builder API endpoints."""

    def test_generate_requires_session(self, client):
        """Test that generate requires a valid session."""
        response = client.post("/api/builder/invalid-session/generate")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_status_requires_session(self, client):
        """Test that status check requires valid session."""
        response = client.get("/api/builder/invalid-session/status")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_requires_completed_generation(self, client, sample_session_data):
        """Test that download requires completed generation."""
        # Create session (but don't run generation)
        create_response = client.post("/api/sessions", json=sample_session_data)
        session_id = create_response.json()["id"]
        
        # Try to download
        response = client.get(f"/api/builder/{session_id}/download")
        
        # Should fail because generation hasn't completed
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]
