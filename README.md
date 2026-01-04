# PersonalTranscribe

A professional voice transcription application built with Python, featuring GPU-accelerated transcription using OpenAI Whisper, synchronized audio playback, and PDF/DOCX export for legal use.

## Features

- **Fast GPU Transcription**: Uses faster-whisper with large-v3 model on NVIDIA GPUs
- **Word-Level Timestamps**: Precise timing for each word with confidence scores
- **Gap Detection**: Shows when the other party is speaking (gaps in your audio)
- **Line-by-Line Editing**: Edit transcriptions with synchronized audio playback
- **Custom Vocabulary**: Add special names and terms for accurate spelling
- **AI Polishing**: Clean up transcripts using OpenAI, Ollama, or other AI providers
- **Recording Metadata**: Add case info, participants, and notes for legal proceedings
- **Multiple Export Formats**: PDF, Word (.docx), SRT subtitles, plain text
- **Project Save/Load**: Save your work and continue later

## Requirements

- Python 3.10+ (3.11 recommended)
- Windows 10/11 (tested), Linux/macOS (should work)
- **For GPU acceleration**: NVIDIA GPU with CUDA support

## Installation

### Option 1: Conda Environment (Recommended for GPU)

Use this method if you have an NVIDIA GPU and want fast transcription:

```bash
# 1. Create and activate the conda environment
conda env create -f environment.yml
conda activate transcribe

# 2. Run the application
python main.py

# Or use the batch file:
.\run_conda.bat
```

### Option 2: UV Package Manager (CPU only, or advanced GPU setup)

Use this method for CPU-only transcription or if you prefer uv:

```powershell
# 1. Install uv (if not already installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Install dependencies
uv sync

# 3. Run the application (use the batch file to set up DLL paths for GPU)
.\run.bat

# Or for CPU-only:
uv run python main.py
```

> **Note**: GPU support with uv requires manual CUDA/cuDNN setup. The conda environment handles this automatically.

## Usage

1. **Open Audio**: File > Open Audio (supports MP3, WAV, M4A, OGG, FLAC)
2. **Add Metadata**: File > Recording Metadata (optional, for legal use)
3. **Transcribe**: Click the Transcribe button - watch progress in the dialog
4. **Edit**: Click any line to edit text, click timestamp to play that segment
5. **Navigate**: Click/drag on waveform, use arrow keys to skip 5 seconds
6. **AI Polish**: Edit > AI Features > Polish Transcript (requires API key or Ollama)
7. **Export**: File > Export to PDF/Word/SRT

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Play/Pause | `Space` |
| Skip Back 5s | `Left Arrow` |
| Skip Forward 5s | `Right Arrow` |
| Replay Last 5s | `R` |
| Loop Segment | `L` |
| Jump to Time | `Ctrl+G` |
| Save Project | `Ctrl+S` |
| Open Audio | `Ctrl+O` |
| Export | `Ctrl+E` |
| Find/Replace | `Ctrl+H` |
| AI Polish | `Ctrl+Shift+P` |
| Recording Metadata | `Ctrl+M` |
| Toggle Dark Mode | `Ctrl+D` |

## Project Structure

```
PersonalTranscribe/
    main.py                 # Application entry point
    pyproject.toml          # UV dependencies
    environment.yml         # Conda environment
    src/
        ai/                 # AI providers (OpenAI, Ollama, etc.)
        config/             # Settings and shortcuts
        export/             # PDF/DOCX/SRT exporters
        models/             # Data structures
        transcription/      # Whisper engine
        ui/                 # PyQt6 widgets
        utils/              # Logging utilities
    resources/
        vocabulary.txt      # Custom words
        themes/             # UI themes (light/dark)
```

## AI Polishing Setup

To use AI transcript polishing:

1. **OpenAI**: Get an API key from [platform.openai.com](https://platform.openai.com)
2. **Ollama** (free, local): Install from [ollama.ai](https://ollama.ai), then `ollama pull llama3.2`
3. Configure in: Edit > AI Features > AI Settings

## Troubleshooting

### GPU not detected
- Ensure you're using the conda environment (`conda activate transcribe`)
- Check NVIDIA drivers are installed: `nvidia-smi`
- The app will fall back to CPU if GPU fails

### Transcription is slow
- MP3 files are converted to WAV automatically (adds ~10 seconds)
- CPU transcription is ~10x slower than GPU
- Consider using a smaller model in settings

### App crashes on large files
- The app uses progressive loading for large transcripts
- Check Help > View Log File for error details

## License

MIT License
