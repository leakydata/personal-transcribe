"""
AI Settings dialog for PersonalTranscribe.
Configure AI providers, API keys, and models.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QPushButton, QTabWidget, QWidget,
    QFormLayout, QMessageBox, QSpinBox, QDoubleSpinBox,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt

from src.ai.provider_base import AIProvider
from src.ai.ai_manager import get_ai_manager
from src.utils.logger import get_logger

logger = get_logger("ui.ai_settings")


class AISettingsDialog(QDialog):
    """Dialog for configuring AI providers."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_manager = get_ai_manager()
        
        self.setWindowTitle("AI Settings")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        self._init_ui()
        self._load_current_settings()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Provider selection
        provider_group = QGroupBox("AI Provider")
        provider_layout = QFormLayout(provider_group)
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "OpenAI (GPT-4, GPT-3.5)",
            "Ollama (Local LLMs)",
            "Google Gemini",
            "Anthropic (Claude)",
            "Deepseek"
        ])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addRow("Provider:", self.provider_combo)
        
        layout.addWidget(provider_group)
        
        # Tab widget for provider-specific settings
        self.tabs = QTabWidget()
        
        # OpenAI tab
        openai_tab = QWidget()
        openai_layout = QFormLayout(openai_tab)
        
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-...")
        openai_layout.addRow("API Key:", self.openai_key_edit)
        
        self.openai_model_combo = QComboBox()
        self.openai_model_combo.addItems([
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo"
        ])
        openai_layout.addRow("Model:", self.openai_model_combo)
        
        self.tabs.addTab(openai_tab, "OpenAI")
        
        # Ollama tab
        ollama_tab = QWidget()
        ollama_layout = QFormLayout(ollama_tab)
        
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        ollama_layout.addRow("Ollama URL:", self.ollama_url_edit)
        
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.addItems([
            "llama3.2",
            "llama3.1",
            "mistral",
            "gemma2",
            "qwen2.5",
            "phi3"
        ])
        ollama_layout.addRow("Model:", self.ollama_model_combo)
        
        refresh_btn = QPushButton("Refresh Models")
        refresh_btn.clicked.connect(self._refresh_ollama_models)
        ollama_layout.addRow("", refresh_btn)
        
        self.tabs.addTab(ollama_tab, "Ollama")
        
        # Gemini tab
        gemini_tab = QWidget()
        gemini_layout = QFormLayout(gemini_tab)
        
        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        gemini_layout.addRow("API Key:", self.gemini_key_edit)
        
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems([
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-1.0-pro"
        ])
        gemini_layout.addRow("Model:", self.gemini_model_combo)
        
        self.tabs.addTab(gemini_tab, "Gemini")
        
        # Anthropic tab
        anthropic_tab = QWidget()
        anthropic_layout = QFormLayout(anthropic_tab)
        
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        anthropic_layout.addRow("API Key:", self.anthropic_key_edit)
        
        self.anthropic_model_combo = QComboBox()
        self.anthropic_model_combo.addItems([
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022"
        ])
        anthropic_layout.addRow("Model:", self.anthropic_model_combo)
        
        self.tabs.addTab(anthropic_tab, "Anthropic")
        
        # Deepseek tab
        deepseek_tab = QWidget()
        deepseek_layout = QFormLayout(deepseek_tab)
        
        self.deepseek_key_edit = QLineEdit()
        self.deepseek_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        deepseek_layout.addRow("API Key:", self.deepseek_key_edit)
        
        self.deepseek_model_combo = QComboBox()
        self.deepseek_model_combo.addItems([
            "deepseek-chat",
            "deepseek-coder"
        ])
        deepseek_layout.addRow("Model:", self.deepseek_model_combo)
        
        self.tabs.addTab(deepseek_tab, "Deepseek")
        
        layout.addWidget(self.tabs)
        
        # Common settings
        common_group = QGroupBox("Polish Settings")
        common_layout = QFormLayout(common_group)
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 1.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.3)
        self.temperature_spin.setToolTip("Lower = more consistent, Higher = more creative")
        common_layout.addRow("Temperature:", self.temperature_spin)
        
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4000)
        self.max_tokens_spin.setValue(2000)
        common_layout.addRow("Max Tokens:", self.max_tokens_spin)
        
        layout.addWidget(common_group)
        
        # Test connection button
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_btn)
        
        self.test_result_label = QLabel("")
        test_layout.addWidget(self.test_result_label, 1)
        
        layout.addLayout(test_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _get_current_provider(self) -> AIProvider:
        """Get the currently selected provider."""
        providers = [
            AIProvider.OPENAI,
            AIProvider.OLLAMA,
            AIProvider.GEMINI,
            AIProvider.ANTHROPIC,
            AIProvider.DEEPSEEK
        ]
        return providers[self.provider_combo.currentIndex()]
    
    def _on_provider_changed(self, index: int):
        """Handle provider selection change."""
        self.tabs.setCurrentIndex(index)
    
    def _load_current_settings(self):
        """Load current settings into the dialog."""
        # Load API keys
        openai_key = self.ai_manager.get_api_key("openai")
        if openai_key:
            self.openai_key_edit.setText(openai_key)
        
        gemini_key = self.ai_manager.get_api_key("gemini")
        if gemini_key:
            self.gemini_key_edit.setText(gemini_key)
        
        anthropic_key = self.ai_manager.get_api_key("anthropic")
        if anthropic_key:
            self.anthropic_key_edit.setText(anthropic_key)
        
        deepseek_key = self.ai_manager.get_api_key("deepseek")
        if deepseek_key:
            self.deepseek_key_edit.setText(deepseek_key)
        
        # Load Ollama URL
        ollama_url = self.ai_manager.get_ollama_url()
        self.ollama_url_edit.setText(ollama_url)
        
        # Load current provider
        current_provider = self.ai_manager.get_configured_provider()
        if current_provider:
            providers = ["openai", "ollama", "gemini", "anthropic", "deepseek"]
            if current_provider in providers:
                self.provider_combo.setCurrentIndex(providers.index(current_provider))
    
    def _refresh_ollama_models(self):
        """Refresh the list of Ollama models."""
        try:
            from src.ai.ollama_provider import OllamaProvider
            from src.ai.provider_base import AIConfig
            
            config = AIConfig(
                provider=AIProvider.OLLAMA,
                base_url=self.ollama_url_edit.text() or "http://localhost:11434"
            )
            provider = OllamaProvider(config)
            models = provider.available_models
            
            if models:
                current = self.ollama_model_combo.currentText()
                self.ollama_model_combo.clear()
                self.ollama_model_combo.addItems(models)
                
                # Restore selection if possible
                idx = self.ollama_model_combo.findText(current)
                if idx >= 0:
                    self.ollama_model_combo.setCurrentIndex(idx)
                
                QMessageBox.information(
                    self, 
                    "Models Refreshed", 
                    f"Found {len(models)} models"
                )
            else:
                QMessageBox.warning(
                    self,
                    "No Models",
                    "No models found. Is Ollama running?"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh models: {e}")
    
    def _test_connection(self):
        """Test the current provider connection."""
        provider = self._get_current_provider()
        
        # Save current settings temporarily
        self._save_current_tab_settings(provider)
        
        self.test_result_label.setText("Testing...")
        self.test_btn.setEnabled(False)
        
        # Force UI update
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            success, message = self.ai_manager.test_provider(provider)
            
            if success:
                self.test_result_label.setText(f"OK: {message}")
                self.test_result_label.setStyleSheet("color: green;")
            else:
                self.test_result_label.setText(f"Failed: {message}")
                self.test_result_label.setStyleSheet("color: red;")
        except Exception as e:
            self.test_result_label.setText(f"Error: {e}")
            self.test_result_label.setStyleSheet("color: red;")
        finally:
            self.test_btn.setEnabled(True)
    
    def _save_current_tab_settings(self, provider: AIProvider):
        """Save settings for the current provider tab."""
        if provider == AIProvider.OPENAI:
            key = self.openai_key_edit.text().strip()
            if key:
                self.ai_manager.set_api_key("openai", key)
            model = self.openai_model_combo.currentText()
            self.ai_manager.set_model("openai", model)
            
        elif provider == AIProvider.OLLAMA:
            url = self.ollama_url_edit.text().strip()
            if url:
                self.ai_manager.set_ollama_url(url)
            model = self.ollama_model_combo.currentText()
            self.ai_manager.set_model("ollama", model)
            
        elif provider == AIProvider.GEMINI:
            key = self.gemini_key_edit.text().strip()
            if key:
                self.ai_manager.set_api_key("gemini", key)
            model = self.gemini_model_combo.currentText()
            self.ai_manager.set_model("gemini", model)
            
        elif provider == AIProvider.ANTHROPIC:
            key = self.anthropic_key_edit.text().strip()
            if key:
                self.ai_manager.set_api_key("anthropic", key)
            model = self.anthropic_model_combo.currentText()
            self.ai_manager.set_model("anthropic", model)
            
        elif provider == AIProvider.DEEPSEEK:
            key = self.deepseek_key_edit.text().strip()
            if key:
                self.ai_manager.set_api_key("deepseek", key)
            model = self.deepseek_model_combo.currentText()
            self.ai_manager.set_model("deepseek", model)
    
    def _save_settings(self):
        """Save all settings and close."""
        provider = self._get_current_provider()
        
        # Save all tab settings
        for p in AIProvider:
            self._save_current_tab_settings(p)
        
        # Set active provider
        self.ai_manager.set_active_provider(provider)
        
        logger.info(f"AI settings saved, active provider: {provider.value}")
        
        QMessageBox.information(
            self,
            "Settings Saved",
            f"AI provider set to: {provider.value}"
        )
        
        self.accept()
