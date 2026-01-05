# PowerShell script to remove all __pycache__ directories and .pyc files
# Run this before testing to ensure no stale bytecode is cached

Write-Host "Cleaning Python cache files..." -ForegroundColor Cyan

# Get the script's directory (project root)
$projectRoot = $PSScriptRoot
if (-not $projectRoot) {
    $projectRoot = Get-Location
}

Write-Host "Project root: $projectRoot" -ForegroundColor Gray

# Remove all __pycache__ directories
$pycacheDirs = Get-ChildItem -Path $projectRoot -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
$pycacheCount = 0

foreach ($dir in $pycacheDirs) {
    Write-Host "  Removing: $($dir.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $pycacheCount++
}

# Remove any stray .pyc files
$pycFiles = Get-ChildItem -Path $projectRoot -File -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
$pycCount = 0

foreach ($file in $pycFiles) {
    Write-Host "  Removing: $($file.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    $pycCount++
}

# Remove any .pyo files (optimized bytecode)
$pyoFiles = Get-ChildItem -Path $projectRoot -File -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
$pyoCount = 0

foreach ($file in $pyoFiles) {
    Write-Host "  Removing: $($file.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    $pyoCount++
}

Write-Host ""
Write-Host "Cleanup complete!" -ForegroundColor Green
Write-Host "  Removed $pycacheCount __pycache__ directories" -ForegroundColor White
Write-Host "  Removed $pycCount .pyc files" -ForegroundColor White
Write-Host "  Removed $pyoCount .pyo files" -ForegroundColor White
Write-Host ""
Write-Host "You can now run the application fresh." -ForegroundColor Cyan
