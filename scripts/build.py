# Builds the site from the map's CellDesigner files (kept in a private repository):
#   python3 scripts/build.py <map folder> [<updated map folder>]
# With an updated folder (the same files with proteins added), every map whose file differs gets a second entry
# right under the original, "<name> (updated)", copied byte for byte into maps-updated/ and drawn as
# drawn/<slug>-updated.svg; maps that did not change appear once.
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


def copy_all(src, out):
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
    return files


def main(src, upd=None):
    global updated, changed
    files = copy_all(src, os.path.join(ROOT, 'maps'))
    updated = upd
    changed = set()
    out_u = os.path.join(ROOT, 'maps-updated')
    if os.path.isdir(out_u):
        shutil.rmtree(out_u)
    if upd:
        ufiles = copy_all(upd, out_u)
        if sorted(ufiles) != sorted(files):
            sys.exit('the updated folder must hold the same files')
        changed = {r for r in files if sha1(os.path.join(src, r)) != sha1(os.path.join(upd, r))}
        # only the changed files are kept in maps-updated/
        for r in ufiles:
            if r not in changed and not r.startswith('glyphs/'):
                os.remove(os.path.join(out_u, r))
    with open(os.path.join(ROOT, 'SHA1SUMS'), 'w', encoding='utf-8') as f:
        for rel in files:
            f.write('%s  maps/%s\n' % (sha1(os.path.join(ROOT, 'maps', rel)), rel))
        for rel in sorted(changed):
            f.write('%s  maps-updated/%s\n' % (sha1(os.path.join(out_u, rel)), rel))
    drawn = os.path.join(ROOT, 'drawn')
    if os.path.isdir(drawn):
        shutil.rmtree(drawn)
    os.makedirs(drawn)
    top = [r for r in files if '/' not in r and r.endswith('.xml')]
    subs = sorted((r for r in files if r.startswith('submaps/') and r.endswith('.xml')), key=lambda r: r.lower())
    maps = []

    def entry_for(folder, rel, name, s, group):
        svg = os.path.join(drawn, s + '.svg')
        r = subprocess.run([sys.executable, RENDER, os.path.join(ROOT, folder, rel), svg], capture_output=True, text=True)
        notes = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
        e = {'name': name, 'slug': s, 'group': group, 'file': folder + '/' + rel, 'sha1': sha1(os.path.join(ROOT, folder, rel)),
             'error': '' if r.returncode == 0 else (notes[-1] if notes else 'not drawn'), 'notes': notes}
        if r.returncode == 0:
            w, h = size(svg)
            e.update({'svg': sha1(svg), 'width': w, 'height': h})
            # what the file says about each process and entity, with where it is drawn (scripts/annotations.py)
            js = os.path.join(drawn, s + '.json')
            a = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'annotations.py'), os.path.join(ROOT, folder, rel), js], capture_output=True, text=True)
            if a.returncode == 0:
                e['ann'] = sha1(js)
            else:
                print('annotations of %s: %s' % (name, (a.stderr.strip().splitlines() or ['failed'])[-1]))
        print('%-70s %s' % (name, e['error'] or ('%d not drawn' % len(notes) if notes else 'ok')))
        return e

    for group, rels in (('Top-level map', top), ('Submaps', subs)):
        for rel in rels:
            name = os.path.basename(rel)[:-4]
            maps.append(entry_for('maps', rel, name, slug(name), group))
            if updated and rel in changed:
                maps.append(dict(entry_for('maps-updated', rel, name + ' (updated)', slug(name) + '-updated', group), updated=True))
    with open(os.path.join(ROOT, 'maps.json'), 'w', encoding='utf-8') as f:
        json.dump(maps, f, indent=1, ensure_ascii=False)
        f.write('\n')


if __name__ == '__main__':
    main(*sys.argv[1:3])
