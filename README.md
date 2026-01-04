# PersonalTranscribe

A professional voice transcription application built with Python, featuring GPU-accelerated transcription using OpenAI Whisper, synchronized audio playback, and PDF export for legal use.

## Features

- **Fast GPU Transcription**: Uses faster-whisper with large-v3 model on NVIDIA GPUs
- **Word-Level Timestamps**: Precise timing for each word with confidence scores
- **Gap Detection**: Shows when the other party is speaking (gaps in your audio)
- **Line-by-Line Editing**: Edit transcriptions with synchronized audio playback
- **Custom Vocabulary**: Add special names and terms for accurate spelling
- **PDF Export**: Professional timestamped exports for legal proceedings
- **Project Save/Load**: Save your work and continue later

## Requirements

- Python 3.10+
- NVIDIA GPU with CUDA support (RTX 4090 recommended)
- CUDA Toolkit 11.x or 12.x

## Installation

1. Install uv (if not already installed):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Install dependencies:
   ```powershell
   uv sync
   ```

3. Run the application:
   ```powershell
   uv run python main.py
   ```

## Usage

1. **Open Audio**: Click File > Open Audio or use the toolbar button
2. **Transcribe**: Click the Transcribe button to process the audio
3. **Edit**: Click any line to edit the text, click timestamp to play that segment
4. **Export**: File > Export to PDF for professional output

## Keyboard Shortcuts

- `Space`: Play/Pause
- `Left/Right Arrow`: Skip 5 seconds
- `L`: Loop current segment
- `Ctrl+S`: Save project
- `Ctrl+O`: Open audio/project
- `Ctrl+E`: Export to PDF

## Project Structure

```
PersonalTranscribe/
    main.py                 # Application entry point
    pyproject.toml          # Dependencies
    src/
        config/             # Settings and shortcuts
        transcription/      # Whisper engine
        ui/                 # PyQt6 widgets
        models/             # Data structures
        export/             # PDF/DOCX exporters
    resources/
        vocabulary.txt      # Custom words
        themes/             # UI themes
```

## License

MIT License
