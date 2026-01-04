"""
Deepseek provider for PersonalTranscribe.
Uses OpenAI-compatible API.
"""

from typing import Optional, List

from src.ai.provider_base import BaseAIProvider, AIConfig, PolishResult
from src.utils.logger import get_logger

logger = get_logger("ai.deepseek")


class DeepseekProvider(BaseAIProvider):
    """Deepseek API provider for text polishing.
    
    Uses OpenAI-compatible API endpoint.
    """
    
    BASE_URL = "https://api.deepseek.com"
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "Deepseek"
    
    @property
    def available_models(self) -> List[str]:
        return [
            "deepseek-chat",
            "deepseek-coder",
        ]
    
    def _get_client(self):
        """Get OpenAI client configured for Deepseek."""
        try:
            from openai import OpenAI
            return OpenAI(
                api_key=self.config.api_key,
                base_url=self.BASE_URL
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    def test_connection(self) -> tuple:
        """Test Deepseek connection."""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.config.model or "deepseek-chat",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=10
            )
            return True, f"Connected to Deepseek ({self.config.model})"
        except Exception as e:
            logger.error(f"Deepseek connection test failed: {e}")
            return False, str(e)
    
    def polish_text(self, text: str, context: Optional[str] = None) -> PolishResult:
        """Polish text using Deepseek."""
        try:
            client = self._get_client()
            prompt = self.get_polish_prompt(text, context)
            
            response = client.chat.completions.create(
                model=self.config.model or "deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional transcription editor. Return only the polished text."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            polished = response.choices[0].message.content.strip()
            changes = self._detect_changes(text, polished)
            
            return PolishResult(
                original_text=text,
                polished_text=polished,
                changes_made=changes
            )
        except Exception as e:
            logger.error(f"Deepseek polish failed: {e}")
            return PolishResult(
                original_text=text,
                polished_text=text,
                changes_made=[f"Error: {e}"]
            )
    
    def polish_batch(
        self,
        texts: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[PolishResult]:
        """Polish multiple texts."""
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            context = texts[i - 1] if i > 0 else None
            result = self.polish_text(text, context)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def _detect_changes(self, original: str, polished: str) -> List[str]:
        """Detect changes made."""
        changes = []
        if original.strip() != polished.strip():
            changes.append("Text refined")
        return changes
