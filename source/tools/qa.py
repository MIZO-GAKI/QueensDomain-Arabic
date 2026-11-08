"""QA: coverage, placeholder/tag parity, untranslated detection, glyph coverage."""
import sys, os, json, glob, re, argparse, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import ttf
ap = argparse.ArgumentParser()
ap.add_argument('--original-pak', help='Recover English source text omitted from the release inventory')
args = ap.parse_args()
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
inv = json.load(open('work/inventory.json', encoding='utf-8'))
sources = {x['id']: x['src'] for x in inv if 'src' in x}
if args.original_pak:
    from pak import Pak
    import locres
    original = Pak(args.original_pak)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'en.locres')
        with open(path, 'wb') as f:
            f.write(original.read('QueensDomain/Content/Localization/Game/en/Game.locres'))
        sources.update({ns + '::' + key: text for _, ns, _, key, _, text in locres.read(path)[1]})
tr = {}
dup = []
for f in sorted(glob.glob('work/translations/*.json')):
    for k, v in json.load(open(f, encoding='utf-8')).items():
        if k in tr: dup.append(k)
        tr[k] = v
ids = {x['id'] for x in inv}
missing = [x['id'] for x in inv if x['id'] not in tr]
extra = [k for k in tr if k not in ids]
ph = re.compile(r'\{[^}]*\}|<[^>]*>')
issues = []
identical = []
# Intentional extra lines: the Arabic localization credit added under the Localization heading of the credits screen.
MULTILINE_OK = {'ImportedStringTable::credits_loc'}
arabic = re.compile('[؀-ۿ]')
for x in inv:
    t = tr.get(x['id'])
    if t is None: continue
    src = sources.get(x['id'])
    if src is not None:
        if sorted(ph.findall(src)) != sorted(ph.findall(t)): issues.append(('placeholder', x['id'], ph.findall(src), ph.findall(t)))
        if src.count('\n') != t.count('\n') and x['id'] not in MULTILINE_OK: issues.append(('newlines', x['id'], src.count('\n'), t.count('\n')))
    if not arabic.search(t): identical.append((x['id'], t))
font = ttf.cmap(open('assets/fonts/NotoNaskhArabicUI-Regular.ttf', 'rb').read())
chars = set(''.join(tr.values()))
nofont = sorted(c for c in chars if '؀' <= c <= 'ۿ' or 'ﭐ' <= c <= '﻿' if ord(c) not in font)
rep = dict(total=len(inv), translated=len(tr) - len(extra), missing=len(missing), extra=extra, duplicates=dup,
           issues=issues, non_arabic=len(identical), glyphs_missing_in_font=nofont,
           source_parity_checked=len(sources), source_parity_unavailable=len(inv)-len(sources))
json.dump(dict(rep, non_arabic_list=identical, missing_list=missing), open('reports/qa.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print({k: (v if not isinstance(v, list) else len(v)) for k, v in rep.items()})
for i in issues: print(i)
if missing or extra or dup or nofont or issues:
    raise SystemExit(1)
