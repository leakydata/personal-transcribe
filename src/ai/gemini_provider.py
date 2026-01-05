"""
Google Gemini provider for PersonalTranscribe.
"""

from typing import Optional, List

from src.ai.provider_base import BaseAIProvider, AIConfig, PolishResult
from src.utils.logger import get_logger

logger = get_logger("ai.gemini")


class GeminiProvider(BaseAIProvider):
    """Google Gemini API provider for text polishing."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "Google Gemini"
    
    @property
    def available_models(self) -> List[str]:
        return [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-1.0-pro",
        ]
    
    def test_connection(self) -> tuple:
        """Test Gemini connection."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.config.api_key)
            model = genai.GenerativeModel(self.config.model or "gemini-1.5-flash")
            response = model.generate_content("Say OK")
            
            return True, f"Connected to Gemini ({self.config.model})"
        except ImportError:
            return False, "google-generativeai package not installed. Run: pip install google-generativeai"
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False, str(e)
    
    def polish_text(
        self, 
        text: str, 
        context_before: Optional[str] = None,
        context_after: Optional[str] = None
    ) -> PolishResult:
        """Polish text using Gemini."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.config.api_key)
            model = genai.GenerativeModel(self.config.model or "gemini-1.5-flash")
            
            prompt = self.get_polish_prompt(text, context_before, context_after)
            response = model.generate_content(prompt)
            polished = response.text.strip()
            
            changes = self._detect_changes(text, polished)
            
            return PolishResult(
                original_text=text,
                polished_text=polished,
                changes_made=changes
            )
        except Exception as e:
            logger.error(f"Gemini polish failed: {e}")
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
