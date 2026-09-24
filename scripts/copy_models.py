"""Copy ready models into the portable app; exclude caches and download archives."""
from pathlib import Path
import shutil

source = Path('models')
target = Path('release/ChineseCap/models')
target.mkdir(parents=True, exist_ok=True)
for name in ('segmentation.onnx', 'embedding.onnx', 'qwen2.5-1.5b-instruct-q4_k_m.gguf', 'deno.exe'):
    if (source / name).is_file():
        shutil.copy2(source / name, target / name)
for name in ('tiny', 'base', 'small', 'medium', 'llama'):
    if (source / name).is_dir():
        shutil.copytree(source / name, target / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.cache', '*.log', '*.partial'))
print(target.resolve())
