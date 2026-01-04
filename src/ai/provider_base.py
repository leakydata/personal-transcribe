"""
Base class for AI providers in PersonalTranscribe.
Defines the interface that all AI providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Generator
from enum import Enum


class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


@dataclass
class AIConfig:
    """Configuration for an AI provider."""
    provider: AIProvider
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # For Ollama or custom endpoints
    model: str = ""
    temperature: float = 0.3  # Low temperature for consistent formatting
    max_tokens: int = 2000


@dataclass
class PolishResult:
    """Result of polishing a text segment."""
    original_text: str
    polished_text: str
    changes_made: List[str]  # List of changes for user review
    confidence: float = 1.0


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: AIConfig):
        self.config = config
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the provider."""
        pass
    
    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """List of available models for this provider."""
        pass
    
    @abstractmethod
    def test_connection(self) -> tuple:
        """Test if the provider is properly configured.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def polish_text(self, text: str, context: Optional[str] = None) -> PolishResult:
        """Polish a single text segment.
        
        Args:
            text: The text to polish
            context: Optional context (previous/next segments for coherence)
            
        Returns:
            PolishResult with original and polished text
        """
        pass
    
    @abstractmethod
    def polish_batch(
        self, 
        texts: List[str], 
        progress_callback: Optional[callable] = None
    ) -> List[PolishResult]:
        """Polish multiple text segments.
        
        Args:
            texts: List of texts to polish
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            List of PolishResult objects
        """
        pass
    
    def get_polish_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Generate the prompt for polishing text.
        
        This can be overridden by subclasses for provider-specific prompts.
        """
        prompt = """You are a professional legal transcription editor. This is verbatim transcription text that may be used in legal proceedings.

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:

1. DO NOT add any words
2. DO NOT remove any words
3. DO NOT change the order of words
4. DO NOT change any words to different words
5. DO NOT correct what you think might be transcription errors

YOU MAY ONLY:
- Add or fix punctuation (periods, commas, question marks, exclamation points)
- Add parentheses, dashes, or ellipses for clarity
- Fix capitalization (start of sentences, proper nouns)
- Fix obvious spelling errors ONLY (like "teh" to "the")

The exact words spoken must remain exactly as transcribed. Every word in your output must be present in the input, in the same order.

If you are unsure about anything, leave it unchanged.

"""
        if context:
            prompt += f"Context (previous text for reference, do not include in output):\n{context}\n\n"
        
        prompt += f"Transcription text to format:\n{text}\n\nFormatted text (same words, only punctuation/capitalization fixed):"
        
        return prompt
