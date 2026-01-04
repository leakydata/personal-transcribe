# PersonalTranscribe Launcher
# This script sets up the NVIDIA DLL paths and launches the application

$ProjectRoot = $PSScriptRoot

# Add NVIDIA DLL paths to PATH
$NvidiaPath = Join-Path $ProjectRoot ".venv\Lib\site-packages\nvidia"
$CudnnBin = Join-Path $NvidiaPath "cudnn\bin"
$CublasBin = Join-Path $NvidiaPath "cublas\bin"

if (Test-Path $CudnnBin) {
    $env:PATH = "$CudnnBin;$env:PATH"
}
if (Test-Path $CublasBin) {
    $env:PATH = "$CublasBin;$env:PATH"
}

# Run the application
Set-Location $ProjectRoot
& "$env:USERPROFILE\.local\bin\uv.exe" run python main.py
