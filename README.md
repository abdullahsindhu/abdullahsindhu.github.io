# Neuroinflammation map viewer

A hidden viewer for the neuroinflammation map: the top-level map and its submaps, each drawn as
CellDesigner draws it, with the CellDesigner file to download. Not indexed (robots.txt, noindex on
every page), no sitemap, not linked from other sites.

- `maps/`: the CellDesigner files, copied byte for byte from the map's source (no annotation, renaming
  or cleanup). `SHA1SUMS` and `maps.json` hold each file's sha1; `sha1sum -c SHA1SUMS` checks the copy.
- `drawn/`: the drawings, made from the files by `converter/cdrender.py` (copied with `converter/mapconv/`
  from the Metabolism Regulation site's converter). The files themselves are not converted.
- `index.html`: the viewer (list, zoom, pan, Fit, full screen, up and down arrow keys, `?map=<name>`).
  A click on a process or an entity opens on the right what its CellDesigner file holds for it: for a
  process what it does, its type, modifiers, references (PubMed, DOI), identifiers and notes; for an
  entity its type, compartment, identifiers and notes. Nothing is shown that the file does not hold.
  `drawn/<name>.json` per map, made by `scripts/annotations.py` during the build.

Rebuild after the map changes:

    python3 scripts/build.py <map folder>

`<map folder>` holds the top-level map, `submaps/` and `glyphs/`. Needs lxml.

Known gaps of the drawing: text layers and the MINERVA glyphs named in the notes are not drawn. Every
line was checked against CellDesigner's PDF exports of five of the maps (within 12 units).
