"""
Ollama provider for PersonalTranscribe.
Supports local LLM models via Ollama.
"""

import json
from typing import Optional, List

from src.ai.provider_base import BaseAIProvider, AIConfig, PolishResult
from src.utils.logger import get_logger

logger = get_logger("ai.ollama")


class OllamaProvider(BaseAIProvider):
    """Ollama local LLM provider for text polishing."""
    
    DEFAULT_URL = "http://localhost:11434"
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self.base_url = config.base_url or self.DEFAULT_URL
    
    @property
    def provider_name(self) -> str:
        return "Ollama (Local)"
    
    @property
    def available_models(self) -> List[str]:
        """Get models from local Ollama instance."""
        try:
            models = self._list_models()
            return models
        except Exception:
            # Return common models if can't connect
            return [
                "llama3.2",
                "llama3.1",
                "mistral",
                "gemma2",
                "qwen2.5",
                "phi3",
            ]
    
    def _list_models(self) -> List[str]:
        """Fetch available models from Ollama."""
        import urllib.request
        import urllib.error
        
        try:
            url = f"{self.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.debug(f"Could not list Ollama models: {e}")
            return []
    
    def test_connection(self) -> tuple:
        """Test Ollama connection."""
        import urllib.request
        import urllib.error
        
        try:
            url = f"{self.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                model_count = len(data.get("models", []))
                return True, f"Connected to Ollama ({model_count} models available)"
        except urllib.error.URLError as e:
            return False, f"Cannot connect to Ollama at {self.base_url}. Is it running?"
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False, str(e)
    
    def polish_text(self, text: str, context: Optional[str] = None) -> PolishResult:
        """Polish a single text segment using Ollama."""
        import urllib.request
        import urllib.error
        
        try:
            prompt = self.get_polish_prompt(text, context)
            
            # Ollama API request
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.config.model or "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                polished = result.get("response", "").strip()
                
                # Clean up response (remove any explanatory text)
                polished = self._clean_response(polished, text)
                
                changes = self._detect_changes(text, polished)
                
                logger.debug(f"Ollama polished: {len(text)} -> {len(polished)} chars")
                
                return PolishResult(
                    original_text=text,
                    polished_text=polished,
                    changes_made=changes
                )
                
        except Exception as e:
            logger.error(f"Ollama polish failed: {e}")
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
            context = texts[i - 1] if i > 0 else None
            result = self.polish_text(text, context)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def _clean_response(self, response: str, original: str) -> str:
        """Clean up LLM response to get just the polished text."""
        # Remove common prefixes that LLMs add
        prefixes_to_remove = [
            "Here is the polished text:",
            "Polished text:",
            "Here's the polished version:",
            "The polished text is:",
        ]
        
        cleaned = response
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove quotes if the whole response is quoted
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]
        
        # If response is much longer than original, it might have explanations
        if len(cleaned) > len(original) * 2:
            # Try to find just the text portion
            lines = cleaned.split("\n")
            if len(lines) > 1:
                # Use only lines that look like transcript text
                text_lines = [l for l in lines if l and not l.startswith(("Note:", "I ", "The ", "Here"))]
                if text_lines:
                    cleaned = " ".join(text_lines)
        
        return cleaned.strip()
    
    def _detect_changes(self, original: str, polished: str) -> List[str]:
        """Detect what changes were made."""
        changes = []
        
        if original.lower() != polished.lower():
            fillers = ["um", "uh", "like", "you know", "basically"]
            for filler in fillers:
                if filler in original.lower() and filler not in polished.lower():
                    changes.append(f"Removed filler: '{filler}'")
            
            orig_puncts = sum(1 for c in original if c in ".,!?;:")
            polish_puncts = sum(1 for c in polished if c in ".,!?;:")
            if polish_puncts > orig_puncts:
                changes.append("Added punctuation")
            
            if not changes:
                changes.append("Text refined")
        
        return changes
