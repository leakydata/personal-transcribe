# PersonalTranscribe

A professional voice transcription application built with Python, featuring GPU-accelerated transcription using OpenAI Whisper, synchronized audio playback, and PDF/DOCX export for legal use.

> **Note**: This project was pair-programmed using [Cursor](https://cursor.sh/) with Claude Opus 4.5 by Anthropic.

| <a href="https://github.com/user-attachments/assets/04bf2449-6036-46e3-a934-4a991edf1e5d"><img src="https://github.com/user-attachments/assets/04bf2449-6036-46e3-a934-4a991edf1e5d" width="400" alt="Transcription Interface" /></a> | <a href="https://github.com/user-attachments/assets/548a4e68-8fa2-4338-972c-2b8c30ed70a1"><img src="https://github.com/user-attachments/assets/548a4e68-8fa2-4338-972c-2b8c30ed70a1" width="400" alt="Settings Interface" /></a> |
| :---: | :---: |

## Features

- **Whisper Transcription**: Uses faster-whisper with selectable models (tiny to large-v3)
- **GPU Acceleration**: NVIDIA CUDA support for 10-15x faster transcription
- **Subprocess Architecture**: Transcription runs in an isolated process for stability
- **Word-Level Timestamps**: Precise timing for each word with confidence scores
- **Gap Detection**: Shows when the other party is speaking (gaps in your audio)
- **Line-by-Line Editing**: Edit transcriptions with synchronized audio playback
- **Custom Vocabulary**: Add special names and terms for accurate spelling
- **AI Polishing**: Clean up transcripts using OpenAI, Ollama, Anthropic, Google Gemini, or DeepSeek
- **Recording Metadata**: Add case info, participants, and notes for legal proceedings
- **Multiple Export Formats**: PDF, Word (.docx), SRT subtitles, VTT
- **Crash Recovery**: Streaming transcription to disk ensures you never lose work
- **Project Save/Load**: Save your work and continue later
- **Segment Merging**: Combine segments that were incorrectly split
- **Speaker Labels**: Assign speakers to segments for multi-party recordings
- **Bookmarks**: Mark important segments for easy navigation

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
    clean_pycache.ps1       # Utility to clean Python cache
    src/
        ai/                 # AI providers (OpenAI, Anthropic, Ollama, Gemini, DeepSeek)
        config/             # Settings and keyboard shortcuts
        export/             # PDF/DOCX/SRT/VTT exporters
        models/             # Data structures (Transcript, Segment, Word)
        transcription/      # Whisper engine and subprocess runner
            whisper_engine.py       # Direct Whisper integration
            transcribe_process.py   # Standalone subprocess for GPU isolation
        ui/                 # PyQt6 widgets
            main_window.py              # Main application window
            transcript_editor.py        # Transcript display and editing
            transcription_dialog.py     # Progress dialog (threaded mode)
            transcription_subprocess_dialog.py  # Progress dialog (subprocess mode)
            audio_player.py             # Waveform and playback
            export_dialog.py            # Export options
            ai_polish_dialog.py         # AI transcript cleaning
        utils/              # Logging utilities
    resources/
        vocabulary.txt      # Custom words for accurate transcription
        themes/             # UI themes (light.qss, dark.qss)
```

## AI Polishing Setup

AI polishing cleans up transcripts by fixing grammar, punctuation, and filler words while preserving the original meaning.

### Supported Providers

| Provider | Type | Setup |
|----------|------|-------|
| **Ollama** | Local, Free | Install from [ollama.ai](https://ollama.ai), run `ollama pull llama3.2` |
| **OpenAI** | Cloud, Paid | Get API key from [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Cloud, Paid | Get API key from [console.anthropic.com](https://console.anthropic.com) |
| **Google Gemini** | Cloud, Free tier | Get API key from [makersuite.google.com](https://makersuite.google.com) |
| **DeepSeek** | Cloud, Cheap | Get API key from [platform.deepseek.com](https://platform.deepseek.com) |

Configure providers in: **AI > AI Settings**

### Polish Modes

- **All Segments**: Polish the entire transcript
- **Selected Segments**: Only polish highlighted segments
- **Time Range**: Polish segments within a specific time range

## Technical Architecture

### Subprocess Transcription

PersonalTranscribe uses a **subprocess architecture** for transcription stability:

1. **Main Process**: Runs the PyQt6 GUI - never loads Whisper/CUDA
2. **Subprocess**: Spawned to run transcription in complete isolation
3. **Communication**: Progress sent via stdout as JSON, transcript saved to disk
4. **Cleanup**: When subprocess exits, OS reclaims ALL GPU memory automatically

This architecture ensures:
- GUI never freezes during transcription
- GPU memory is always properly released
- Crashes in transcription don't take down the UI
- Long transcriptions (1+ hours) are stable

### Streaming to Disk

During transcription, segments are saved to disk every 50 segments:
- Location: `%LOCALAPPDATA%\PersonalTranscribe\streaming\`
- Format: JSON with full word-level timestamps
- If anything fails, use **File > Recover Transcription**

## Troubleshooting

### GPU not detected
- Ensure you're using the conda environment (`conda activate transcribe`)
- Check NVIDIA drivers are installed: `nvidia-smi`
- The app will fall back to CPU if GPU fails

### Transcription is slow
- Compressed audio (MP3, M4A) is converted to WAV automatically (adds ~10 seconds)
- CPU transcription is ~10x slower than GPU
- Try a smaller model: Transcription > Whisper Model > Small

### Subprocess crashes on long files
- The transcript is saved periodically - use **File > Recover Transcription**
- Check `%LOCALAPPDATA%\PersonalTranscribe\streaming\` for partial transcripts
- Even if subprocess crashes, completed segments are preserved

### App uses too much memory
- Large transcripts (1000+ segments) use pagination automatically
- Each page shows 100 segments to reduce memory usage
- Use the page navigation buttons at the bottom of the transcript

### Export fails
- Ensure you have a transcript loaded
- Check that the audio file path is still valid
- Try saving the project first, then exporting

## Credits

This project was developed using:
- [Cursor](https://cursor.sh/) - AI-powered code editor
- [Claude Opus 4.5](https://www.anthropic.com/) by Anthropic - AI pair programming assistant
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Optimized Whisper implementation
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework

## License

MIT License
