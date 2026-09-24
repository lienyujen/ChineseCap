param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& $Python -m PyInstaller --noconfirm --windowed --name ChineseCap --icon assets\ChineseCap.ico --distpath release --onedir --collect-all faster_whisper --collect-all ctranslate2 --collect-all sherpa_onnx --collect-all onnxruntime --collect-all opencc --collect-all tokenizers --collect-all yt_dlp --collect-all yt_dlp_ejs --copy-metadata huggingface-hub main.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
& $Python scripts/fix_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Bundle validation failed' }
Copy-Item -LiteralPath 'README.md' -Destination 'release\ChineseCap\使用說明.md' -Force
Copy-Item -LiteralPath 'THIRD_PARTY.md' -Destination 'release\ChineseCap\THIRD_PARTY.md' -Force
Copy-Item -LiteralPath 'assets\ChineseCap.ico' -Destination 'release\ChineseCap\ChineseCap.ico' -Force
& $Python scripts/collect_licenses.py
Write-Host '完成：release\ChineseCap\ChineseCap.exe。請保留整個 ChineseCap 資料夾。'
