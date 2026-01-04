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
        prompt = """You are a professional transcription editor. Your task is to polish the following transcribed text while preserving the speaker's meaning exactly.

Rules:
1. Fix punctuation and capitalization
2. Remove filler words (um, uh, you know, like) only if they don't add meaning
3. Fix obvious transcription errors if context makes the correct word clear
4. Split run-on sentences appropriately
5. Format numbers, dates, and times properly
6. DO NOT change the meaning or add information
7. DO NOT make the language more formal than it was
8. Preserve the speaker's voice and style

"""
        if context:
            prompt += f"Context (previous text for reference):\n{context}\n\n"
        
        prompt += f"Text to polish:\n{text}\n\nPolished text:"
        
        return prompt
