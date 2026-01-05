"""
Anthropic (Claude) provider for PersonalTranscribe.
"""

from typing import Optional, List

from src.ai.provider_base import BaseAIProvider, AIConfig, PolishResult
from src.utils.logger import get_logger

logger = get_logger("ai.anthropic")


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude API provider for text polishing."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "Anthropic (Claude)"
    
    @property
    def available_models(self) -> List[str]:
        return [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
        ]
    
    def test_connection(self) -> tuple:
        """Test Anthropic connection."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.config.api_key)
            message = client.messages.create(
                model=self.config.model or "claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}]
            )
            
            return True, f"Connected to Claude ({self.config.model})"
        except ImportError:
            return False, "anthropic package not installed. Run: pip install anthropic"
        except Exception as e:
            logger.error(f"Anthropic connection test failed: {e}")
            return False, str(e)
    
    def polish_text(
        self, 
        text: str, 
        context_before: Optional[str] = None,
        context_after: Optional[str] = None
    ) -> PolishResult:
        """Polish text using Claude."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.config.api_key)
            prompt = self.get_polish_prompt(text, context_before, context_after)
            
            message = client.messages.create(
                model=self.config.model or "claude-3-haiku-20240307",
                max_tokens=self.config.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            polished = message.content[0].text.strip()
            changes = self._detect_changes(text, polished)
            
            return PolishResult(
                original_text=text,
                polished_text=polished,
                changes_made=changes
            )
        except Exception as e:
            logger.error(f"Anthropic polish failed: {e}")
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
