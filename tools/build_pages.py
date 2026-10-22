"""Package static, browser-local preview assets for GitHub Pages."""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/'dist'
OUTPUT.mkdir(exist_ok=True)
for name in ('index.html','style.css','app.js','browser-store.js','upstash-store.js','learning.js','tutor.js'):
    shutil.copyfile(ROOT/'app'/'static'/name,OUTPUT/name)
shutil.copyfile(ROOT/'content'/'exam-question-bank.json',OUTPUT/'question-bank.json')
(OUTPUT/'config.js').write_text("window.REVISION_CONFIG = { storage: 'browser' };\n")
(OUTPUT/'.nojekyll').touch()
assert len(json.loads((OUTPUT/'question-bank.json').read_text())['questions'])>=400
assert 'href="./style.css"' in (OUTPUT/'index.html').read_text()
print('Built static preview in dist/; observations stay in the visitor browser.')
