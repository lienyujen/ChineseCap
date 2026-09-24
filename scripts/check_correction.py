import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chinesecap.core import load_project, export
from chinesecap.corrector import LocalCorrector

if __name__ == '__main__':
    source = sorted(Path('test-artifacts').glob('four-speakers_*/專案.json'))[-1]
    cues, meta = load_project(source)
    for c in cues:
        c.notes = [n for n in c.notes if '校正失敗' not in n]
    with LocalCorrector(Path('models').resolve(), 4, print, None) as corrector:
        corrector.correct(cues, '')
    dest = export(cues, Path('test-artifacts'), 'corrected', meta)
    print(dest)
    for c in cues:
        print(c.raw, '=>', c.text, c.notes)
