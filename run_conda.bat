@echo off
REM Launch PersonalTranscribe using conda environment
call conda activate transcribe
cd /d "%~dp0"
python main.py
