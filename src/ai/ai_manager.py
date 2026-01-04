"""
AI Manager for PersonalTranscribe.
Handles provider selection, configuration, and polishing operations.
"""

import json
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from src.ai.provider_base import BaseAIProvider, AIConfig, AIProvider, PolishResult
from src.utils.logger import get_logger

logger = get_logger("ai.manager")


class AIManager:
    """Manages AI providers and polishing operations."""
    
    CONFIG_FILE = "ai_config.json"
    
    def __init__(self):
        self._provider: Optional[BaseAIProvider] = None
        self._config: Optional[AIConfig] = None
        self._settings: Dict[str, Any] = {}
        self._load_settings()
    
    def _get_config_path(self) -> Path:
        """Get path to AI config file."""
        # Store in app data directory
        import sys
        if sys.platform == "win32":
            app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            config_dir = Path(app_data) / "PersonalTranscribe"
        else:
            config_dir = Path.home() / ".personaltranscribe"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / self.CONFIG_FILE
    
    def _load_settings(self):
        """Load AI settings from config file."""
        config_path = self._get_config_path()
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    self._settings = json.load(f)
                logger.debug(f"Loaded AI settings from {config_path}")
            except Exception as e:
                logger.error(f"Failed to load AI settings: {e}")
                self._settings = {}
        else:
            self._settings = {}
    
    def _save_settings(self):
        """Save AI settings to config file."""
        config_path = self._get_config_path()
        
        try:
            with open(config_path, "w") as f:
                json.dump(self._settings, f, indent=2)
            logger.debug(f"Saved AI settings to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save AI settings: {e}")
    
    def get_configured_provider(self) -> Optional[str]:
        """Get the currently configured provider name."""
        return self._settings.get("provider")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        keys = self._settings.get("api_keys", {})
        return keys.get(provider)
    
    def set_api_key(self, provider: str, api_key: str):
        """Set API key for a provider."""
        if "api_keys" not in self._settings:
            self._settings["api_keys"] = {}
        self._settings["api_keys"][provider] = api_key
        self._save_settings()
        logger.info(f"API key set for {provider}")
    
    def get_model(self, provider: str) -> Optional[str]:
        """Get selected model for a provider."""
        models = self._settings.get("models", {})
        return models.get(provider)
    
    def set_model(self, provider: str, model: str):
        """Set model for a provider."""
        if "models" not in self._settings:
            self._settings["models"] = {}
        self._settings["models"][provider] = model
        self._save_settings()
    
    def get_ollama_url(self) -> str:
        """Get Ollama base URL."""
        return self._settings.get("ollama_url", "http://localhost:11434")
    
    def set_ollama_url(self, url: str):
        """Set Ollama base URL."""
        self._settings["ollama_url"] = url
        self._save_settings()
    
    def configure_provider(self, provider: AIProvider) -> AIConfig:
        """Create configuration for a provider."""
        config = AIConfig(
            provider=provider,
            api_key=self.get_api_key(provider.value),
            base_url=self.get_ollama_url() if provider == AIProvider.OLLAMA else None,
            model=self.get_model(provider.value) or self._default_model(provider),
            temperature=self._settings.get("temperature", 0.3),
            max_tokens=self._settings.get("max_tokens", 2000)
        )
        return config
    
    def _default_model(self, provider: AIProvider) -> str:
        """Get default model for a provider."""
        defaults = {
            AIProvider.OPENAI: "gpt-4o-mini",
            AIProvider.OLLAMA: "llama3.2",
            AIProvider.GEMINI: "gemini-1.5-flash",
            AIProvider.ANTHROPIC: "claude-3-haiku-20240307",
            AIProvider.DEEPSEEK: "deepseek-chat",
        }
        return defaults.get(provider, "")
    
    def get_provider(self, provider_type: AIProvider) -> BaseAIProvider:
        """Get an AI provider instance."""
        config = self.configure_provider(provider_type)
        
        if provider_type == AIProvider.OPENAI:
            from src.ai.openai_provider import OpenAIProvider
            return OpenAIProvider(config)
        elif provider_type == AIProvider.OLLAMA:
            from src.ai.ollama_provider import OllamaProvider
            return OllamaProvider(config)
        elif provider_type == AIProvider.GEMINI:
            from src.ai.gemini_provider import GeminiProvider
            return GeminiProvider(config)
        elif provider_type == AIProvider.ANTHROPIC:
            from src.ai.anthropic_provider import AnthropicProvider
            return AnthropicProvider(config)
        elif provider_type == AIProvider.DEEPSEEK:
            from src.ai.deepseek_provider import DeepseekProvider
            return DeepseekProvider(config)
        else:
            raise ValueError(f"Unknown provider: {provider_type}")
    
    def set_active_provider(self, provider: AIProvider):
        """Set the active provider."""
        self._settings["provider"] = provider.value
        self._save_settings()
        self._provider = self.get_provider(provider)
        logger.info(f"Active AI provider set to {provider.value}")
    
    def get_active_provider(self) -> Optional[BaseAIProvider]:
        """Get the currently active provider."""
        provider_name = self.get_configured_provider()
        if provider_name:
            try:
                provider_type = AIProvider(provider_name)
                return self.get_provider(provider_type)
            except Exception as e:
                logger.error(f"Failed to get active provider: {e}")
        return None
    
    def test_provider(self, provider_type: AIProvider) -> tuple:
        """Test a provider's connection.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            provider = self.get_provider(provider_type)
            return provider.test_connection()
        except Exception as e:
            return False, str(e)
    
    def polish_segments(
        self,
        segments: List[str],
        provider_type: Optional[AIProvider] = None,
        progress_callback: Optional[callable] = None
    ) -> List[PolishResult]:
        """Polish a list of text segments.
        
        Args:
            segments: List of text strings to polish
            provider_type: Optional provider to use (uses active if not specified)
            progress_callback: Optional callback(current, total)
            
        Returns:
            List of PolishResult objects
        """
        if provider_type:
            provider = self.get_provider(provider_type)
        else:
            provider = self.get_active_provider()
        
        if not provider:
            raise ValueError("No AI provider configured")
        
        logger.info(f"Polishing {len(segments)} segments with {provider.provider_name}")
        
        return provider.polish_batch(segments, progress_callback)


# Global manager instance
_ai_manager: Optional[AIManager] = None


def get_ai_manager() -> AIManager:
    """Get the global AI manager instance."""
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIManager()
    return _ai_manager
