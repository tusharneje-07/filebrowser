$appName = "filebrowser"
$installDir = "$HOME\AppData\Local\$appName"
$binDir = "$HOME\AppData\Local\Microsoft\WindowsApps"

Write-Host "Installing $appName..."

if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir
}

# Check for python
try {
    python --version
} catch {
    Write-Host "Python is required but not installed. Please install it from python.org."
    exit
}

# Setup venv
python -m venv "$installDir\venv"
& "$installDir\venv\Scripts\pip.exe" install flask werkzeug Pillow pystray

# Create wrapper batch file
$batchContent = @"
@echo off
"$installDir\venv\Scripts\python.exe" "$installDir\tray_server.py" %*
"@
$batchContent | Out-File -FilePath "$binDir\$appName.bat" -Encoding ascii

Write-Host "Installation complete. You can run '$appName' from your command prompt."
