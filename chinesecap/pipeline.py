from __future__ import annotations

import gc
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .core import make_cues
from .models import check, deno_path, missing


@dataclass
class Options:
    source: str
    root: Path
    asr: str = 'medium'
    diarize: bool = True
    speakers: int = 0
    correction: bool = True
    threads: int = 4
    glossary: str = ''
    acceleration: str = 'auto'


def youtube_url(source: str) -> bool:
    url = urlparse(source)
    return (url.scheme in ('http', 'https') and
            url.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com'))


def cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except (ImportError, RuntimeError, OSError):
        return False


def load_whisper_model(model_path: Path, acceleration: str, threads: int, log):
    from faster_whisper import WhisperModel
    if acceleration not in ('auto', 'cuda', 'cpu'):
        raise ValueError('不支援的運算裝置設定')
    wants_cuda = acceleration == 'cuda' or (acceleration == 'auto' and cuda_available())
    if wants_cuda:
        try:
            model = WhisperModel(str(model_path), device='cuda', compute_type='int8_float16',
                                 local_files_only=True)
            log('中文語音辨識：NVIDIA GPU / CUDA INT8-FP16')
            return model, 'cuda'
        except (RuntimeError, OSError) as error:
            if acceleration == 'cuda':
                raise RuntimeError('NVIDIA GPU 啟動失敗。請確認驅動程式、CUDA 12、cuBLAS 與 cuDNN 9 已安裝。'
                                   f' 原始錯誤：{error}') from error
            log(f'NVIDIA GPU 無法啟動，已安全退回 CPU：{error}')
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8',
                         cpu_threads=threads, local_files_only=True)
    log('中文語音辨識：CPU INT8')
    return model, 'cpu'


def run(options: Options, log, progress, cancel):
    from faster_whisper.audio import decode_audio
    missing_files = missing(options.root, options.asr, options.diarize, options.correction)
    if missing_files:
        raise RuntimeError('模型尚未準備完成，請先按「下載／準備模型」。\n' + '\n'.join(missing_files))
    if not youtube_url(options.source) and not Path(options.source).is_file():
        raise ValueError('請選擇存在的影音檔，或輸入單支 YouTube 影片網址')
    with tempfile.TemporaryDirectory(prefix='ChineseCap-') as temp:
        source = options.source
        if youtube_url(source):
            from yt_dlp import YoutubeDL
            deno = deno_path(options.root)
            if not deno.exists():
                raise RuntimeError('YouTube 執行元件尚未安裝，請先按「下載／準備模型」。')
            log('下載 YouTube 音訊（需要網路）…')
            def hook(_):
                check(cancel)
            with YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True,
                'js_runtimes': {'deno': {'path': str(deno)}},
                'outtmpl': str(Path(temp) / 'source.%(ext)s'), 'quiet': True,
                'progress_hooks': [hook], 'socket_timeout': 30,
                'match_filter': lambda info, **kwargs: '不支援直播，請使用已結束的影片' if info.get('is_live') else None}) as ydl:
                info = ydl.extract_info(source, download=True)
                if not info:
                    raise RuntimeError('無法下載此影片')
                source = ydl.prepare_filename(info)
        check(cancel)
        log('解碼影音為 16 kHz 單聲道…')
        audio = decode_audio(source, sampling_rate=16000)
        duration = len(audio) / 16000
        if duration == 0:
            raise ValueError('檔案沒有可讀取的音訊')
        progress(5)
        turns = None
        if options.diarize:
            import sherpa_onnx as so
            log('分析聲紋與說話者區間…')
            config = so.OfflineSpeakerDiarizationConfig(
                segmentation=so.OfflineSpeakerSegmentationModelConfig(
                    pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(
                        model=str(options.root / 'segmentation.onnx')),
                    num_threads=options.threads, provider='cpu'),
                embedding=so.SpeakerEmbeddingExtractorConfig(
                    model=str(options.root / 'embedding.onnx'),
                    num_threads=options.threads, provider='cpu'),
                clustering=so.FastClusteringConfig(num_clusters=options.speakers or -1, threshold=.5),
                min_duration_on=.3, min_duration_off=.5)
            if not config.validate():
                raise RuntimeError('聲紋模型設定無效')
            sd = so.OfflineSpeakerDiarization(config)
            def diar_progress(done, total):
                check(cancel)
                progress(5 + int(25 * done / max(total, 1)))
                return 0
            rows = sd.process(audio, callback=diar_progress).sort_by_start_time()
            # Stable IDs by first appearance, not arbitrary clustering indices.
            mapping = {}
            turns = []
            for row in rows:
                mapping.setdefault(row.speaker, len(mapping))
                turns.append((row.start, row.end, mapping[row.speaker]))
            del sd
            gc.collect()
        check(cancel)
        log(f'載入 Whisper {options.asr}…')
        model, actual_device = load_whisper_model(options.root / options.asr,
                                                   options.acceleration, options.threads, log)
        segments, _ = model.transcribe(audio, language='zh', beam_size=5,
            vad_filter=True, word_timestamps=True, condition_on_previous_text=False,
            initial_prompt='以下是台灣中文對話。' + options.glossary[:1000])
        words = []
        for seg in segments:
            check(cancel)
            if seg.words:
                for w in seg.words:
                    # Whisper occasionally yields overlapping or out-of-range word timestamps.
                    start = max(0., w.start, words[-1][1] if words else 0.)
                    end = min(duration, max(start, w.end))
                    if end > start:
                        words.append((start, end, w.word))
            else:
                start = max(0., seg.start, words[-1][1] if words else 0.)
                if min(duration, seg.end) > start:
                    words.append((start, min(duration, seg.end), seg.text))
            progress(30 + int(50 * min(seg.end / duration, 1)))
            log(f'已辨識 {seg.end:.0f} / {duration:.0f} 秒')
        del model, audio
        gc.collect()
        cues = make_cues(words, turns)
        if not cues:
            raise RuntimeError('沒有辨識到語音，請確認音軌與音量')
        if options.correction:
            from .corrector import LocalCorrector
            log('載入本機文字模型，依上下文清理贅字與校正…')
            with LocalCorrector(options.root, options.threads, log, cancel) as corrector:
                corrector.correct(cues, options.glossary)
        check(cancel)
        progress(100)
        metadata = {'source': options.source, 'duration': duration, 'asr': options.asr,
            'diarization': options.diarize, 'requested_speakers': options.speakers,
            'correction': options.correction, 'glossary': options.glossary,
            'acceleration_requested': options.acceleration, 'asr_device': actual_device,
            'notice': '模型推測的清理稿，請核對專有名詞、語意及說話者。'}
        return cues, metadata
