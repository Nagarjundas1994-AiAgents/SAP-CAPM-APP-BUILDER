"""
Tests for provider model catalog helpers.
"""

from unittest.mock import AsyncMock, patch

from backend.model_catalog import _normalize_openrouter_models, _parse_xai_models_markdown


class TestXAIModelCatalog:
    """Tests for xAI catalog parsing."""

    def test_parse_xai_markdown_deduplicates_and_skips_image_models(self):
        markdown = """
| Model | Modalities | Capabilities | Context | Rate Limits | Pricing [in (cached in) / out] |
| --- | --- | --- | --- | --- | --- |
| grok-4.20-beta-0309-reasoning | text, image -> text | functions, structured, reasoning | 2,000,000 | 4M TPM, 607 RPM | $2.00 / $6.00 |
| grok-4.20-beta-0309-reasoning | text, image -> text | functions, structured, reasoning | 2,000,000 | 4M TPM, 607 RPM | $2.00 / $6.00 |
| grok-code-fast-1 | text -> text | functions, structured, reasoning | 256,000 | 2M TPM, 2,125 RPM | $0.20 / $1.50 |
| grok-imagine-image | text, image -> image | - | - | 300 RPM | $0.02/image |
"""

        models = _parse_xai_models_markdown(markdown)

        assert [model["id"] for model in models] == [
            "grok-4.20-beta-0309-reasoning",
            "grok-code-fast-1",
        ]
        assert models[0]["recommended"] is True
        assert models[1]["recommended"] is False


class TestOpenRouterModelCatalog:
    """Tests for OpenRouter catalog normalization."""

    def test_normalize_openrouter_filters_old_and_non_text_models(self):
        records = [
            {
                "id": "qwen/qwen3-coder:free",
                "name": "Qwen: Qwen3 Coder",
                "created": 1736294400,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 262144,
                "description": "Free coding model",
            },
            {
                "id": "legacy/old-model",
                "name": "Old Model",
                "created": 1733011200,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "context_length": 32768,
                "description": "Should be filtered out",
            },
            {
                "id": "image/model",
                "name": "Image Model",
                "created": 1736294400,
                "architecture": {
                    "input_modalities": ["image"],
                    "output_modalities": ["image"],
                },
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 8192,
                "description": "Not suitable for the builder chat flow",
            },
        ]

        models = _normalize_openrouter_models(records)

        assert len(models) == 1
        assert models[0]["id"] == "qwen/qwen3-coder:free"
        assert models[0]["pricing_type"] == "free"
        assert models[0]["recommended"] is True


class TestModelCatalogEndpoint:
    """Tests for the public model catalog endpoint."""

    def test_config_endpoint_lists_supported_providers(self, client):
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        provider_ids = [provider["id"] for provider in data["supported_providers"]]
        assert "xai" in provider_ids
        assert "openrouter" in provider_ids

    def test_models_endpoint_returns_live_provider_payload(self, client):
        mocked_models = [
            {
                "id": "grok-4.20-beta-0309-reasoning",
                "name": "Grok 4.20 Beta 0309 Reasoning",
                "label": "Grok 4.20 Beta 0309 Reasoning (Paid)",
                "pricing_type": "paid",
                "price_summary": "$2.00 / $6.00",
                "created_at": None,
                "context_length": 2000000,
                "description": "Current xAI reasoning model.",
                "source": "https://docs.x.ai/docs/models.md",
                "recommended": True,
            }
        ]

        with patch(
            "backend.model_catalog.get_provider_models",
            new=AsyncMock(return_value=("xai_docs", mocked_models)),
        ):
            response = client.get("/api/config/models?provider=xai")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "xai"
        assert data["source"] == "xai_docs"
        assert data["models"][0]["id"] == "grok-4.20-beta-0309-reasoning"
