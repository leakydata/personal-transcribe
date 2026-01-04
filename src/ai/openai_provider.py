"""
OpenAI provider for PersonalTranscribe.
Supports GPT-4, GPT-4o, GPT-3.5-turbo models.
"""

from typing import Optional, List
import json

from src.ai.provider_base import BaseAIProvider, AIConfig, PolishResult, AIProvider
from src.utils.logger import get_logger

logger = get_logger("ai.openai")


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider for text polishing."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._client = None
    
    @property
    def provider_name(self) -> str:
        return "OpenAI"
    
    @property
    def available_models(self) -> List[str]:
        return [
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
    
    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.config.api_key)
                logger.debug("OpenAI client initialized")
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Run: uv add openai"
                )
        return self._client
    
    def test_connection(self) -> tuple:
        """Test OpenAI connection."""
        try:
            client = self._get_client()
            # Simple test call
            response = client.chat.completions.create(
                model=self.config.model or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}],
                max_tokens=10
            )
            return True, f"Connected to OpenAI ({self.config.model})"
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False, str(e)
    
    def polish_text(self, text: str, context: Optional[str] = None) -> PolishResult:
        """Polish a single text segment using OpenAI."""
        try:
            client = self._get_client()
            
            prompt = self.get_polish_prompt(text, context)
            
            response = client.chat.completions.create(
                model=self.config.model or "gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional transcription editor. Return only the polished text, nothing else."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            polished = response.choices[0].message.content.strip()
            
            # Detect changes
            changes = self._detect_changes(text, polished)
            
            logger.debug(f"Polished text: {len(text)} -> {len(polished)} chars, {len(changes)} changes")
            
            return PolishResult(
                original_text=text,
                polished_text=polished,
                changes_made=changes
            )
            
        except Exception as e:
            logger.error(f"OpenAI polish failed: {e}")
            # Return original text on error
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
        """Polish multiple text segments."""
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            # Use previous segment as context if available
            context = texts[i - 1] if i > 0 else None
            
            result = self.polish_text(text, context)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def _detect_changes(self, original: str, polished: str) -> List[str]:
        """Detect what changes were made between original and polished text."""
        changes = []
        
        # Simple change detection
        if original.lower() != polished.lower():
            # Check for filler word removal
            fillers = ["um", "uh", "like", "you know", "basically", "actually"]
            for filler in fillers:
                if filler in original.lower() and filler not in polished.lower():
                    changes.append(f"Removed filler: '{filler}'")
            
            # Check for punctuation changes
            orig_puncts = sum(1 for c in original if c in ".,!?;:")
            polish_puncts = sum(1 for c in polished if c in ".,!?;:")
            if polish_puncts > orig_puncts:
                changes.append("Added punctuation")
            
            # Check for capitalization
            if original[0].islower() and polished[0].isupper():
                changes.append("Fixed capitalization")
            
            # If we couldn't detect specific changes, note general edit
            if not changes:
                changes.append("Text refined")
        
        return changes
