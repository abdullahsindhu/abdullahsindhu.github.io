# Builds the site from the map's CellDesigner files (kept in a private repository):
#   python3 scripts/build.py <map folder>
# <map folder> holds the top-level map (one .xml), submaps/ and glyphs/. Every file is copied
# into maps/ byte for byte (no annotation, renaming or cleanup), each .xml is drawn as
# CellDesigner draws it (converter/cdrender.py) into drawn/<slug>.svg, and maps.json and
# SHA1SUMS record each file's sha1, so any change to a file is visible. The copy is checked
# against the source after writing. Needs lxml.
import hashlib, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, 'converter', 'cdrender.py')


def sha1(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def size(svg):
    m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', open(svg, encoding='utf-8').read(4000))
    return float(m.group(1)), float(m.group(2))


def main(src):
    out = os.path.join(ROOT, 'maps')
    if os.path.isdir(out):
        shutil.rmtree(out)
    files = []
    for d, _, names in os.walk(src):
        for n in sorted(names):
            files.append(os.path.relpath(os.path.join(d, n), src))
    files.sort()
    for rel in files:
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(src, rel), dst)
        if sha1(dst) != sha1(os.path.join(src, rel)):
            sys.exit('copy differs: ' + rel)
    with open(os.path.join(ROOT, 'SHA1SUMS'), 'w', encoding='utf-8') as f:
        for rel in files:
            f.write('%s  maps/%s\n' % (sha1(os.path.join(out, rel)), rel))

    drawn = os.path.join(ROOT, 'drawn')
    if os.path.isdir(drawn):
        shutil.rmtree(drawn)
    os.makedirs(drawn)
    top = [r for r in files if '/' not in r and r.endswith('.xml')]
    subs = sorted((r for r in files if r.startswith('submaps/') and r.endswith('.xml')), key=lambda r: r.lower())
    maps = []
    for group, rels in (('Top-level map', top), ('Submaps', subs)):
        for rel in rels:
            name = os.path.basename(rel)[:-4]
            s = slug(name)
            svg = os.path.join(drawn, s + '.svg')
            r = subprocess.run([sys.executable, RENDER, os.path.join(out, rel), svg], capture_output=True, text=True)
            notes = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
            entry = {'name': name, 'slug': s, 'group': group, 'file': 'maps/' + rel, 'sha1': sha1(os.path.join(out, rel)),
                     'error': '' if r.returncode == 0 else (notes[-1] if notes else 'not drawn'), 'notes': notes}
            if r.returncode == 0:
                w, h = size(svg)
                entry.update({'svg': sha1(svg), 'width': w, 'height': h})
            maps.append(entry)
            print('%-70s %s' % (name, entry['error'] or '%d not drawn' % len(notes) if notes else 'ok'))
    with open(os.path.join(ROOT, 'maps.json'), 'w', encoding='utf-8') as f:
        json.dump(maps, f, indent=1, ensure_ascii=False)
        f.write('\n')


if __name__ == '__main__':
    main(sys.argv[1])
