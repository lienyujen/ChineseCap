"""Avoid an unrelated ICU from the build host shadowing Windows' native ICU.

Qt's Windows build imports unversioned ICU symbols. Some Python build environments
put a renamed ICU 78 on PATH whose exports are suffixed _78; PyInstaller may collect
that incompatible DLL. Preserve it as a disabled file and let Windows resolve its
native ICU, as it does when running the original PySide6 wheel.
"""
from pathlib import Path
import pefile

path = Path('release/ChineseCap/_internal/icuuc.dll')
if path.exists():
    pe = pefile.PE(str(path))
    symbols = {item.name for item in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    pe.close()
    if b'ucnv_open' not in symbols:
        path.replace(path.with_suffix('.dll.disabled'))
        print('Disabled incompatible build-host ICU; Qt will use Windows ICU.')
