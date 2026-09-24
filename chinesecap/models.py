from __future__ import annotations

import hashlib
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

LLAMA_URL = 'https://github.com/ggml-org/llama.cpp/releases/download/b10964/llama-b10964-bin-win-cpu-x64.zip'
LLAMA_SHA = '917f39c076402c421224824607397af20f53625a60defc20e8dd22446bf4c5d7'
SEG_URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2'
EMBED_URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx'
LLM_FILE = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
RUNTIMES = {
    'windows-x64': {
        'llama_url': LLAMA_URL, 'llama_sha': LLAMA_SHA,
        'deno_url': 'https://github.com/denoland/deno/releases/download/v2.9.6/deno-x86_64-pc-windows-msvc.zip',
        'deno_sha': '15e5300b0ba3c3695a7621d90160a746ec9e710228cee639afa9d580f6e3cd11',
        'deno': 'deno.exe', 'llama': 'llama-server.exe'},
    'macos-arm64': {
        'llama_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b10964/llama-b10964-bin-macos-arm64.tar.gz',
        'llama_sha': '033c845c1df9bf945ff37bb193238b40910b2244be3e1e637b2ceb5878f1a6f5',
        'deno_url': 'https://github.com/denoland/deno/releases/download/v2.9.6/deno-aarch64-apple-darwin.zip',
        'deno_sha': '213a2f304f04d3c9cb5220669afad138f60a5aab1fe80962abdeb8f35807a472',
        'deno': 'deno', 'llama': 'llama-server'},
    'macos-x64': {
        'llama_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b10964/llama-b10964-bin-macos-x64.tar.gz',
        'llama_sha': '03430a394d0a169a5e6d8f01c09f48cf58eb026af6fc95940a4a528e2e50cf38',
        'deno_url': 'https://github.com/denoland/deno/releases/download/v2.9.6/deno-x86_64-apple-darwin.zip',
        'deno_sha': '7d4524b82bcc557fe020a1a5b56956ed42b992ae5b28026e8ad5d17329533f5f',
        'deno': 'deno', 'llama': 'llama-server'},
}


class Cancelled(Exception):
    pass


def check(cancel):
    if cancel and cancel.is_set():
        raise Cancelled('已取消')


def runtime_info() -> dict:
    machine = platform.machine().lower()
    if os.name == 'nt' and machine in ('amd64', 'x86_64'):
        return RUNTIMES['windows-x64']
    if sys.platform == 'darwin':
        return RUNTIMES['macos-arm64' if machine in ('arm64', 'aarch64') else 'macos-x64']
    raise RuntimeError(f'目前尚未提供此平台的執行元件：{sys.platform} / {machine}')


def deno_path(root: Path) -> Path:
    return root / runtime_info()['deno']


def llama_server_path(root: Path) -> Path:
    return root / 'llama' / runtime_info()['llama']


def default_root() -> Path:
    portable = Path(__file__).resolve().parent.parent / 'models'
    import sys
    if getattr(sys, 'frozen', False):
        portable = Path(sys.executable).parent / 'models'
    if portable.exists():
        return portable
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ChineseCap' / 'models'
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ChineseCap' / 'models'


def download(url: str, dest: Path, log, cancel=None, sha: str | None = None):
    if dest.exists() and (not sha or hashlib.sha256(dest.read_bytes()).hexdigest() == sha):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + '.partial')
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={'User-Agent': 'ChineseCap/0.1'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response, temp.open('wb') as out:
            total = int(response.headers.get('Content-Length', 0))
            done, reported = 0, -1
            while block := response.read(1024 * 1024):
                check(cancel)
                out.write(block)
                digest.update(block)
                done += len(block)
                bucket = done // (20 * 1024 * 1024)
                if bucket != reported:
                    log(f'下載 {dest.name}：{done // 1048576} / {total // 1048576 or "?"} MB')
                    reported = bucket
        if sha and digest.hexdigest() != sha:
            raise RuntimeError(f'{dest.name} 雜湊驗證失敗，請重新下載')
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)


def install(root: Path, asr: str, diarize: bool, correction: bool, log, cancel=None):
    from huggingface_hub import snapshot_download, hf_hub_download
    root.mkdir(parents=True, exist_ok=True)
    prepare_youtube(root, log, cancel)
    check(cancel)
    log(f'準備 Whisper {asr}（首次下載可能需要幾分鐘）')
    snapshot_download(f'Systran/faster-whisper-{asr}', local_dir=str(root / asr),
                      allow_patterns=['*.json', '*.txt', '*.bin'])
    check(cancel)
    if diarize:
        archive = root / 'segmentation.tar.bz2'
        segment = root / 'segmentation.onnx'
        if not segment.exists():
            download(SEG_URL, archive, log, cancel)
            with tarfile.open(archive) as tar:
                member = next(m for m in tar.getmembers() if m.name.endswith('/model.onnx') and m.isfile())
                with tar.extractfile(member) as src, segment.with_suffix('.partial').open('wb') as dst:
                    shutil.copyfileobj(src, dst)
            segment.with_suffix('.partial').replace(segment)
        download(EMBED_URL, root / 'embedding.onnx', log, cancel)
    check(cancel)
    if correction:
        log('下載 Qwen2.5 1.5B Q4_K_M 上下文校正模型（約 1 GB）')
        hf_hub_download('Qwen/Qwen2.5-1.5B-Instruct-GGUF', LLM_FILE, local_dir=str(root))
        check(cancel)
        runtime_info_value = runtime_info()
        suffix = '.tar.gz' if runtime_info_value['llama_url'].endswith('.tar.gz') else '.zip'
        archive = root / f'llama-cpu{suffix}'
        download(runtime_info_value['llama_url'], archive, log, cancel, runtime_info_value['llama_sha'])
        runtime = root / 'llama'
        runtime.mkdir(exist_ok=True)
        if suffix == '.zip':
            with zipfile.ZipFile(archive) as z:
                for archive_info in z.infolist():
                    name = Path(archive_info.filename).name
                    if name.lower().endswith(('.dll', '.exe')):
                        with z.open(archive_info) as src, (runtime / name).open('wb') as dst:
                            shutil.copyfileobj(src, dst)
        else:
            with tarfile.open(archive) as tar:
                for archive_info in tar.getmembers():
                    if not archive_info.isfile():
                        continue
                    name = Path(archive_info.name).name
                    if name == runtime_info_value['llama'] or name.endswith('.dylib'):
                        with tar.extractfile(archive_info) as src, (runtime / name).open('wb') as dst:
                            shutil.copyfileobj(src, dst)
                        (runtime / name).chmod(0o755)
    log('模型已準備完成；本機影音可離線處理。')


def prepare_youtube(root: Path, log, cancel=None):
    info = runtime_info()
    binary = deno_path(root)
    if binary.exists():
        return
    archive = root / 'deno.zip'
    download(info['deno_url'], archive, log, cancel, info['deno_sha'])
    with zipfile.ZipFile(archive) as z:
        member = next(n for n in z.namelist() if Path(n).name == info['deno'])
        with z.open(member) as src, binary.with_suffix('.partial').open('wb') as dst:
            shutil.copyfileobj(src, dst)
    binary.with_suffix('.partial').replace(binary)
    binary.chmod(0o755)


def missing(root: Path, asr: str, diarize: bool, correction: bool) -> list[str]:
    paths = [root / asr / name for name in ['model.bin', 'config.json', 'tokenizer.json']]
    if diarize:
        paths += [root / 'segmentation.onnx', root / 'embedding.onnx']
    if correction:
        paths += [root / LLM_FILE, llama_server_path(root)]
    return [str(p) for p in paths if not p.is_file()]
