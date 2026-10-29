# manifest

The JSON index the Voice Director reads. One entry per spoken line. Planned, not built yet.

## Planned schema (one entry)
```json
{
  "id": "c0142",
  "character": "corvus",
  "text": "That, Bastion, is what the film room was for.",
  "pieces": [
    { "file": "lines/corvus/c0142__01.ogg", "text": "That," },
    { "file": "lines/corvus/c0142__02.ogg", "text": "Bastion, is what the film room was for." }
  ],
  "pauses": [250],
  "intensity": 1,
  "duration_ms": 3180,
  "sha": "<hash of text + voice + speed + generator version>"
}
```

## Fields
- `id`: unique line id; also the clip filename prefix.
- `character`: `corvus` or `bastion`.
- `text`: the full line as written, with blanks like `{team}` where a name clip goes.
- `pieces[]`: the clips in play order. A piece is a file, or a blank to fill from `names/` or `common/`.
- `pauses`: gap in milliseconds after each piece (one fewer than pieces). These come from the pause marks in `booth-lines.js`.
- `intensity`: 0 calm, 1 normal, 2 excited. Lets the Director pick the right variant of a line.
- `duration_ms`: total length with gaps, so the Director can plan overlaps and interjections.
- `sha`: hash used to skip regenerating a clip when nothing changed (the one-generation rule).
