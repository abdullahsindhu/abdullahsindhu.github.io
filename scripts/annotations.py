# What a CellDesigner file says about its reactions and species, with where each is drawn, for the
# viewer's panel (user, 2026-11-03: click a process to see its PMIDs; only what the file has):
#   python3 scripts/annotations.py <map.xml> <out.json>
# Reactions: what they do (reactants, products, modifiers by name), their type, references (PubMed, DOI),
# other identifiers and notes. Species: name, type, compartment, identifiers and notes ("Glyph: ..." notes
# are MINERVA image names, left out). Geometry from converter/cdrender.py (render_hits): each alias's box,
# each reaction's lines and square. Nothing is added that the file does not hold.
import json, os, re, sys
from urllib.parse import unquote
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'converter'))
import cdrender  # noqa: E402
from mapconv.celldesigner import plain_name  # noqa: E402

C = '{http://www.sbml.org/2001/ns/celldesigner}'
S = '{http://www.sbml.org/sbml/level2/version4}'
RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'

DB = {'pubmed': 'PubMed', 'doi': 'DOI', 'uniprot': 'UniProt', 'obo.go': 'GO', 'obo.chebi': 'ChEBI', 'pdb': 'PDB',
      'mesh': 'MeSH', 'ncbigene': 'NCBI Gene', 'hgnc': 'HGNC', 'hgnc.symbol': 'HGNC symbol', 'refseq': 'RefSeq',
      'ensembl': 'Ensembl', 'interpro': 'InterPro', 'taxonomy': 'Taxonomy', 'string': 'STRING',
      'pubchem.compound': 'PubChem compound', 'pubchem.substance': 'PubChem substance', 'rhea': 'Rhea', 'pfam': 'Pfam',
      'pirsf': 'PIRSF', 'chembl.compound': 'ChEMBL', 'reactome': 'Reactome', 'bind': 'BIND'}
RELATION = {'is': 'is', 'isDescribedBy': 'described by', 'isEncodedBy': 'encoded by', 'isPartOf': 'part of',
            'isVersionOf': 'version of', 'hasVersion': 'has version', 'hasPart': 'has part', 'isHomologTo': 'homolog of',
            'occursIn': 'occurs in', 'hasProperty': 'has property', 'encodes': 'encodes'}


def link(ns, i):
    if ns == 'pubmed':
        return 'https://pubmed.ncbi.nlm.nih.gov/%s/' % i
    if ns == 'doi':
        return 'https://doi.org/%s' % i
    if ns == 'uniprot':
        return 'https://www.uniprot.org/uniprotkb/%s' % i
    if ns.startswith('obo.'):  # GO:0043197, CHEBI:2910
        return 'https://identifiers.org/%s' % i
    return 'https://identifiers.org/%s:%s' % (ns, i)


def identifiers(e):
    out, seen = [], set()
    for li in e.iter(RDF + 'li'):
        m = re.match(r'urn:miriam:([^:]+):(.+)$', li.get(RDF + 'resource') or '')
        if not m:
            continue
        ns, i = m.group(1), unquote(m.group(2)).strip()
        q = li.getparent().getparent()
        rel = etree.QName(q).localname if q is not None else ''
        if (ns, i) in seen:
            continue
        seen.add((ns, i))
        out.append({'db': DB.get(ns, ns), 'id': i, 'url': link(ns, i), 'rel': RELATION.get(rel, rel)})
    return out


def notes(e):
    for q in (S + 'notes', C + 'notes'):
        n = e.find(q)
        if n is not None:
            lines = [' '.join(l.split()) for l in '\n'.join(n.itertext()).split('\n')]
            return '\n'.join(l for l in lines if l and not l.startswith('Glyph:'))
    return ''


def name(n):
    return ' '.join(plain_name(n or '').replace('_br_', ' ').split())


WORD = {'CATALYSIS': 'catalysis', 'UNKNOWN_CATALYSIS': 'unknown catalysis', 'INHIBITION': 'inhibition',
        'UNKNOWN_INHIBITION': 'unknown inhibition', 'TRIGGER': 'trigger', 'PHYSICAL_STIMULATION': 'stimulation',
        'MODULATION': 'modulation', 'TRANSCRIPTIONAL_ACTIVATION': 'transcriptional activation',
        'TRANSCRIPTIONAL_INHIBITION': 'transcriptional inhibition', 'TRANSLATIONAL_ACTIVATION': 'translational activation',
        'TRANSLATIONAL_INHIBITION': 'translational inhibition'}


def main(xml, out):
    svg, hits = cdrender.render_hits(xml)
    t = etree.parse(xml)
    model = t.getroot().find(S + 'model')
    comp = {c.get('id'): name(c.get('name') or '') for c in model.iter(S + 'compartment')}
    sp = {}
    for s in list(model.iter(S + 'species')) + list(model.iter(C + 'species')):
        cls = s.find('.//' + C + 'class')
        c = s.get('compartment') or ''
        sp[s.get('id')] = {'name': name(s.get('name')), 'class': cls.text if cls is not None else '',
                           'compartment': comp.get(c, '') if c != 'default' else '', 'ids': identifiers(s), 'notes': notes(s)}
    alias_species = {a['id']: a['species'] for a in hits['aliases']}
    nm = lambda e: sp.get(e.get('species') or e.get('reactant') or e.get('product') or '', {}).get('name') or \
        sp.get(alias_species.get(e.get('alias'), ''), {}).get('name', '')
    reactions = []
    for rx in model.iter(S + 'reaction'):
        x = rx.find(S + 'annotation/' + C + 'extension')
        if x is None:
            continue
        ins = [nm(e) for e in x.iterfind(C + 'baseReactants/' + C + 'baseReactant')] + \
              [nm(e) for e in x.iterfind(C + 'listOfReactantLinks/' + C + 'reactantLink')]
        outs = [nm(e) for e in x.iterfind(C + 'baseProducts/' + C + 'baseProduct')] + \
               [nm(e) for e in x.iterfind(C + 'listOfProductLinks/' + C + 'productLink')]
        mods, gated = [], set()
        ml = list(x.iterfind(C + 'listOfModification/' + C + 'modification'))
        for m in ml:
            if (m.get('type') or '').startswith('BOOLEAN_LOGIC_GATE'):
                al = (m.get('aliases') or '').split(',')
                gated |= {(a, m.get('modificationType')) for a in al}
                kind = m.get('type').rsplit('_', 1)[1]
                mods.append({'by': (' %s ' % kind).join(sp.get(alias_species.get(a, ''), {}).get('name', '') for a in al),
                             'how': WORD.get(m.get('modificationType'), (m.get('modificationType') or '').lower())})
        for m in ml:
            if (m.get('type') or '').startswith('BOOLEAN_LOGIC_GATE') or (m.get('aliases'), m.get('type')) in gated:
                continue
            mods.append({'by': sp.get(alias_species.get(m.get('aliases'), ''), {}).get('name', ''),
                         'how': WORD.get(m.get('type'), (m.get('type') or '').lower().replace('_', ' '))})
        typ = x.findtext(C + 'reactionType') or ''
        if typ == 'BOOLEAN_LOGIC_GATE':
            gm = [g for g in x.iterfind(C + 'listOfGateMember/' + C + 'GateMember') if (g.get('type') or '').startswith('BOOLEAN')]
            if gm:
                ins = [(' %s ' % gm[0].get('type').rsplit('_', 1)[1]).join(sp.get(alias_species.get(a, ''), {}).get('name', '')
                                                                         for a in gm[0].get('aliases').split(','))]
        ids = identifiers(rx)
        h = hits['reactions'].get(rx.get('id'), {'lines': [], 'at': None})
        reactions.append({'what': ' + '.join(ins) + ' → ' + ' + '.join(outs), 'type': typ.lower().replace('_', ' '),
                          'reversible': rx.get('reversible') != 'false', 'modifiers': mods,
                          'refs': [i for i in ids if i['db'] in ('PubMed', 'DOI')],
                          'ids': [i for i in ids if i['db'] not in ('PubMed', 'DOI')],
                          'notes': notes(rx), 'lines': h['lines'], 'at': h['at']})
    aliases = []
    used = {}
    for a in hits['aliases']:
        s = a['species']
        if s not in used:
            used[s] = len(used)
        aliases.append({'box': a['box'], 'species': used[s]})
    species = [None] * len(used)
    for s, k in used.items():
        species[k] = sp.get(s, {'name': '', 'class': '', 'compartment': '', 'ids': [], 'notes': ''})
    # smaller boxes first, so a member is found before the complex around it
    aliases.sort(key=lambda a: a['box'][2] * a['box'][3])
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'species': species, 'aliases': aliases, 'reactions': reactions}, f, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
