@echo off
REM PersonalTranscribe Launcher
REM This script sets up the NVIDIA DLL paths and launches the application

cd /d "%~dp0"

REM Add NVIDIA DLL paths to PATH
set "NVIDIA_PATH=%~dp0.venv\Lib\site-packages\nvidia"
set "PATH=%NVIDIA_PATH%\cudnn\bin;%NVIDIA_PATH%\cublas\bin;%PATH%"

REM Run the application
"%USERPROFILE%\.local\bin\uv.exe" run python main.py
