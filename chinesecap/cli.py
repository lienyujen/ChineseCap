import argparse
import json
from pathlib import Path
from threading import Event
from .core import export
from .pipeline import Options, run


def main():
    parser = argparse.ArgumentParser(description='ChineseCap local transcription')
    parser.add_argument('--batch', required=True, help='Local media or YouTube URL')
    parser.add_argument('--models', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--speakers', type=int, default=0)
    parser.add_argument('--no-correction', action='store_true')
    parser.add_argument('--device', choices=('auto', 'cuda', 'cpu'), default='auto')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'batch.log').open('w', encoding='utf-8') as stream:
        def log(message):
            stream.write(message + '\n')
            stream.flush()
        try:
            cues, metadata = run(Options(args.batch, args.models.resolve(),
                speakers=args.speakers, correction=not args.no_correction,
                acceleration=args.device), log, lambda _: None, Event())
            path = export(cues, args.output, 'ChineseCap', metadata)
            result = {'status': 'ok', 'output': str(path.resolve()), 'cues': len(cues)}
        except Exception as error:
            result = {'status': 'error', 'error': str(error)}
        (args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0 if result['status'] == 'ok' else 1
