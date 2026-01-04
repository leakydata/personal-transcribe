# PersonalTranscribe

A professional voice transcription application built with Python, featuring GPU-accelerated transcription using OpenAI Whisper, synchronized audio playback, and PDF/DOCX export for legal use.

> **Note**: This project was pair-programmed using [Cursor](https://cursor.sh/) with Claude Opus 4.5 by Anthropic.

## Features

- **Whisper Transcription**: Uses faster-whisper with selectable models (tiny to large-v3)
- **GPU Acceleration**: NVIDIA CUDA support for 10-15x faster transcription
- **Word-Level Timestamps**: Precise timing for each word with confidence scores
- **Gap Detection**: Shows when the other party is speaking (gaps in your audio)
- **Line-by-Line Editing**: Edit transcriptions with synchronized audio playback
- **Custom Vocabulary**: Add special names and terms for accurate spelling
- **AI Polishing**: Clean up transcripts using OpenAI, Ollama, or other AI providers
- **Recording Metadata**: Add case info, participants, and notes for legal proceedings
- **Multiple Export Formats**: PDF, Word (.docx), SRT subtitles
- **Crash Recovery**: Streaming transcription to disk ensures you never lose work
- **Project Save/Load**: Save your work and continue later

## Whisper Models

Choose the right model for your hardware:

| Model | Size | Speed | Accuracy | Recommended For |
|-------|------|-------|----------|-----------------|
| tiny | ~75MB | Fastest | Basic | Quick previews, testing |
| base | ~140MB | Fast | Fair | Low-end hardware |
| small | ~460MB | Medium | Good | Balanced performance |
| medium | ~1.5GB | Slower | Better | Good accuracy without GPU |
| large-v3 | ~3GB | Slowest | Best | Professional use (GPU recommended) |

Change models via: **Transcription > Whisper Model**

## Requirements

- Python 3.10+ (3.11 recommended)
- Windows 10/11 (tested), Linux/macOS (should work)
- **For GPU acceleration**: NVIDIA GPU with CUDA support

### Hardware Recommendations

- **With GPU (RTX 3060+)**: Use `large-v3` model for best accuracy
- **Without GPU**: Use `small` or `medium` model for reasonable speed
- **Low-end PC**: Use `tiny` or `base` model

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
2. **Select Model**: Transcription > Whisper Model (choose based on your hardware)
3. **Add Metadata**: File > Recording Metadata (optional, for legal use)
4. **Transcribe**: Click the Transcribe button - watch progress in the dialog
5. **Edit**: Click any line to edit text, click timestamp to play that segment
6. **Navigate**: Click/drag on waveform, use arrow keys to skip 5 seconds
7. **AI Polish**: AI > Polish Transcript (requires API key or Ollama)
8. **Export**: File > Export to PDF/Word/SRT
9. **Recover**: File > Recover Transcription (if app crashed during transcription)

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

## Crash Recovery

PersonalTranscribe automatically saves your work during transcription:

- **Streaming files**: Each segment is saved as it's transcribed
- **Autosave files**: Complete transcripts saved before UI loading

If the app crashes, use **File > Recover Transcription** to restore your work.

Recovery files are stored in:
- `%LOCALAPPDATA%\PersonalTranscribe\streaming\` (partial transcriptions)
- `%LOCALAPPDATA%\PersonalTranscribe\autosave\` (complete transcriptions)

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
3. Configure in: AI > AI Settings

## Troubleshooting

### GPU not detected
- Ensure you're using the conda environment (`conda activate transcribe`)
- Check NVIDIA drivers are installed: `nvidia-smi`
- The app will fall back to CPU if GPU fails

### Transcription is slow
- MP3 files are converted to WAV automatically (adds ~10 seconds)
- CPU transcription is ~10x slower than GPU
- Try a smaller model: Transcription > Whisper Model > Small

### App crashes on large files
- Transcription streams to disk - use File > Recover Transcription
- The app uses simplified display for large transcripts (>100 segments)
- Check Help > View Log File for error details

## Credits

This project was developed using:
- [Cursor](https://cursor.sh/) - AI-powered code editor
- [Claude Opus 4.5](https://www.anthropic.com/) by Anthropic - AI pair programming assistant
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Optimized Whisper implementation
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework

## License

MIT License
