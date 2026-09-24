"""Retain package-supplied licenses in a distributable folder."""
from importlib.metadata import distributions
from pathlib import Path
import shutil

root = Path('release/ChineseCap/licenses')
for dist in distributions():
    name = dist.metadata.get('Name', 'unknown')
    for file in dist.files or []:
        if any(token in file.name.lower() for token in ('license', 'copying', 'notice')):
            source = Path(dist.locate_file(file))
            if source.is_file() and source.suffix.lower() not in ('.py', '.pyc', '.pyd'):
                target = root / name / str(file).replace('..', '_')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
