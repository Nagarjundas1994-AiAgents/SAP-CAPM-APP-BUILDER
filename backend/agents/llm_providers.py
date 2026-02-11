"""
Multi-LLM Provider Abstraction Layer
Supports OpenAI GPT-4, Google Gemini, DeepSeek, and Kimi K2.5
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        """Get LangChain chat model instance."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        messages: list[BaseMessage],
        **kwargs,
    ) -> str:
        """Generate a response from messages."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4 provider."""
    
    @property
    def name(self) -> str:
        return "openai"
    
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key
        self.model = model
    
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=kwargs.get("temperature", 0.1),
            **kwargs,
        )
    
    async def generate(self, messages: list[BaseMessage], **kwargs) -> str:
        model = self.get_chat_model(**kwargs)
        logger.info(f"LLM Generation: provider={self.name}, model={self.model}")
        response = await model.ainvoke(messages)
        return str(response.content)


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""
    
    @property
    def name(self) -> str:
        return "gemini"
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model
    
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                google_api_key=self.api_key,
                model=self.model,
                temperature=kwargs.get("temperature", 0.1),
                convert_system_message_to_human=True,
                **kwargs,
            )
        except ImportError:
            raise ImportError("langchain-google-genai is required for Gemini support")
    
    async def generate(self, messages: list[BaseMessage], **kwargs) -> str:
        model = self.get_chat_model(**kwargs)
        logger.info(f"LLM Generation: provider={self.name}, model={self.model}")
        response = await model.ainvoke(messages)
        return str(response.content)


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider (OpenAI-compatible API)."""
    
    @property
    def name(self) -> str:
        return "deepseek"
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"
    
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            temperature=kwargs.get("temperature", 0.1),
            **kwargs,
        )
    
    async def generate(self, messages: list[BaseMessage], **kwargs) -> str:
        model = self.get_chat_model(**kwargs)
        logger.info(f"LLM Generation: provider={self.name}, model={self.model}")
        response = await model.ainvoke(messages)
        return str(response.content)


class KimiProvider(LLMProvider):
    """Kimi (Moonshot) K2.5 provider (OpenAI-compatible API)."""
    
    @property
    def name(self) -> str:
        return "kimi"
    
    def __init__(self, api_key: str, model: str = "moonshot-v1-128k"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.moonshot.cn/v1"
    
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            temperature=kwargs.get("temperature", 0.1),
            **kwargs,
        )
    
    async def generate(self, messages: list[BaseMessage], **kwargs) -> str:
        model = self.get_chat_model(**kwargs)
        response = await model.ainvoke(messages)
        return str(response.content)


class LLMManager:
    """
    Central manager for LLM providers.
    Handles provider selection, fallback, and configuration.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._providers: dict[str, LLMProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize available providers based on API keys."""
        if self.settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                model=self.settings.llm_models["openai"],
            )
            logger.info("OpenAI provider initialized")
        
        if self.settings.google_api_key:
            self._providers["gemini"] = GeminiProvider(
                api_key=self.settings.google_api_key,
                model=self.settings.llm_models["gemini"],
            )
            logger.info("Gemini provider initialized")
        
        if self.settings.deepseek_api_key:
            self._providers["deepseek"] = DeepSeekProvider(
                api_key=self.settings.deepseek_api_key,
                model=self.settings.llm_models["deepseek"],
            )
            logger.info("DeepSeek provider initialized")
        
        if self.settings.kimi_api_key:
            self._providers["kimi"] = KimiProvider(
                api_key=self.settings.kimi_api_key,
                model=self.settings.llm_models["kimi"],
            )
            logger.info("Kimi provider initialized")
    
    @property
    def available_providers(self) -> list[str]:
        """List of available provider names."""
        return list(self._providers.keys())
    
    def get_provider(self, name: str | None = None) -> LLMProvider:
        """
        Get a specific provider or the default one.
        
        Args:
            name: Provider name. If None, uses default from settings.
            
        Returns:
            LLMProvider instance
            
        Raises:
            ValueError: If provider is not available
        """
        provider_name = name or self.settings.default_llm_provider
        
        if provider_name not in self._providers:
            available = ", ".join(self.available_providers) or "none"
            raise ValueError(
                f"Provider '{provider_name}' is not available. "
                f"Available providers: {available}. "
                f"Please configure the API key in .env"
            )
        
        return self._providers[provider_name]
    
    def get_chat_model(
        self,
        provider: str | None = None,
        **kwargs,
    ) -> BaseChatModel:
        """
        Get a LangChain chat model for use in LangGraph.
        
        Args:
            provider: Provider name (optional, uses default)
            **kwargs: Additional model configuration
            
        Returns:
            LangChain BaseChatModel instance
        """
        return self.get_provider(provider).get_chat_model(**kwargs)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response using the specified provider.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            provider: Provider name (optional)
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        messages: list[BaseMessage] = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        llm_provider = self.get_provider(provider)
        return await llm_provider.generate(messages, **kwargs)


# Global LLM manager instance
_llm_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    """Get the global LLM manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
