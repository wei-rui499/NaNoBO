"""Check a frozen PYZ with its matching Python major/minor version."""
import json
import sys
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
root=Path(__file__).resolve().parents[1]
executable=Path(sys.argv[1])
archive=CArchiveReader(str(executable)).open_embedded_archive('PYZ.pyz')
checks={}
for name in sys.argv[2:]:
    frozen=archive.extract('chembo.'+name)
    current=compile((root/'src/chembo'/(name+'.py')).read_text(encoding='utf-8'),frozen.co_filename,'exec',dont_inherit=True)
    checks[executable.name+':'+name]=frozen==current
print(json.dumps(checks))
raise SystemExit(0 if all(checks.values()) else 1)
