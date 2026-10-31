// validate-manifest.mjs: check manifest/manifest.json against the schema in manifest/README.md and the Voice Director.
// Usage: node tools/validate-manifest.mjs [manifest.json] [--files] [--lines booth-lines.js]
//   --files  also check every clip file exists (paths are relative to the repo root)
//   --lines  also check every line in booth-lines.js has an entry, and that each entry's pieces line up with
//            speechPieces() the same way the Director's resolve() walks them
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { createRequire } from 'node:module';

const args = process.argv.slice(2);
const path = resolve(args.find(a => !a.startsWith('--') && args[args.indexOf(a) - 1] !== '--lines') || 'manifest/manifest.json');
const root = resolve(dirname(path), '..');
const checkFiles = args.includes('--files');
const linesArg = args.includes('--lines') ? args[args.indexOf('--lines') + 1] : null;
const m = JSON.parse(readFileSync(path, 'utf8'));
const errs = [], warns = [];
const err = (s) => errs.push(s), warn = (s) => warns.push(s);
const isClip = (f) => typeof f === 'string' && /^(lines|names|common|reactions|interjections)\/[a-z0-9_\-/]+\.(ogg|wav)$/.test(f);
const fileOk = (f, where) => { if (!isClip(f)) err(`${where}: bad clip path ${JSON.stringify(f)}`); else if (checkFiles && !existsSync(join(root, f))) err(`${where}: missing file ${f}`); };

if (!Array.isArray(m.lines)) err('lines must be an array');
if (m.base != null && typeof m.base !== 'string') err('base must be a string');
const ids = new Set();
for (const e of m.lines || []) {
  const w = `line ${e.id}`;
  if (!e.id || typeof e.id !== 'string') { err('line without id'); continue; }
  if (ids.has(e.id)) err(`${w}: duplicate id`); ids.add(e.id);
  if (!['corvus', 'bastion'].includes(e.character)) err(`${w}: character must be corvus or bastion`);
  if (typeof e.text !== 'string' || !e.text) err(`${w}: text missing`);
  if (!Array.isArray(e.pieces) || !e.pieces.length) { err(`${w}: pieces missing`); continue; }
  e.pieces.forEach((p, i) => {
    if (p.slot) { if (typeof p.slot !== 'string') err(`${w} piece ${i}: slot must be a name`); return; }
    fileOk(p.file, `${w} piece ${i}`);
    if (typeof p.text !== 'string') err(`${w} piece ${i}: text missing`);
  });
  if (!Array.isArray(e.pauses) || e.pauses.length !== e.pieces.length - 1) err(`${w}: pauses must have one fewer entry than pieces`);
  else if (e.pauses.some(x => !Number.isInteger(x) || x < 0 || x > 3000)) err(`${w}: pause out of range`);
  if (![1, 2, 3].includes(e.intensity)) err(`${w}: intensity must be 1, 2 or 3`);
  if (!Number.isFinite(e.duration_ms) || e.duration_ms <= 0) err(`${w}: duration_ms missing`);
  if (typeof e.sha !== 'string' || !e.sha) err(`${w}: sha missing`);
  if (e.overlap_piece != null && !(e.overlap_piece >= 0 && e.overlap_piece <= e.pieces.length)) err(`${w}: overlap_piece out of range`);
}
for (const k of ['names', 'common', 'reactions', 'interjections']) {
  const map = m[k] || {};
  if (typeof map !== 'object' || Array.isArray(map)) { err(`${k} must be an object`); continue; }
  for (const [key, f] of Object.entries(map)) {
    if ((k === 'names' || k === 'common') && !/^[a-z0-9-]+(@(corvus|bastion))?$/.test(key)) err(`${k}.${key}: key must be a slug (voice-director slug()) with optional @corvus/@bastion`);
    fileOk(f, `${k}.${key}`);
  }
}

function segments(pieces) { // copy of voice-director.js segments() (v9.4.0)
  const segs = [];
  for (const p of pieces || []) {
    const last = segs[segs.length - 1];
    if (p.text != null) { if (last && last.kind === 'text' && !last.closed) last.text += ' ' + p.text; else segs.push({ kind: 'text', text: p.text }); }
    else if (p.slot) { if (last) last.closed = true; segs.push({ kind: 'slot', slot: p.slot }); }
    else if (p.pause != null) { if (last) last.closed = true; segs.push({ kind: 'pause', ms: Number(p.pause) || 0 }); }
    else if (p.overlap) { if (last) last.closed = true; }
  }
  return { segs };
}
if (linesArg) {
  const B = createRequire(import.meta.url)(resolve(linesArg));
  // voice-director.js next to booth-lines.js when it is there, else the same segments() rule copied here
  const vdPath = resolve(dirname(resolve(linesArg)), 'voice-director.js');
  const VD = existsSync(vdPath) ? createRequire(import.meta.url)(vdPath) : { segments };
  const byId = Object.fromEntries((m.lines || []).map(e => [e.id, e]));
  let missing = 0, checked = 0;
  const each = (id, raw) => {
    const e = byId[id]; if (!e) { missing++; return; }
    const { segs } = VD.segments(B.speechPieces(raw), {});
    const texts = segs.filter(s => s.kind === 'text').length, files = e.pieces.filter(p => p.file).length;
    const slots = segs.filter(s => s.kind === 'slot').length, mslots = e.pieces.filter(p => p.slot).length;
    if (texts !== files || slots !== mslots) err(`line ${id}: ${files} clips / ${mslots} fill-ins, but the Director plays ${texts} text runs / ${slots} fill-ins`);
    checked++;
  };
  for (const t of B.triggers) for (const w of Object.keys(B.lines[t])) B.lines[t][w].forEach((l, i) => each(`${t}:${w}:${i}`, l));
  for (const t of Object.keys(B.tiers)) for (const w of Object.keys(B.tiers[t])) for (const n of Object.keys(B.tiers[t][w])) B.tiers[t][w][n].forEach((l, i) => each(`${t}:${w}:t${n}:${i}`, l));
  if (missing) warn(`${missing} booth lines have no manifest entry yet (the Director skips them for sound)`);
  for (const who of Object.keys(B.reactions)) for (const r of B.reactions[who]) if (!(m.reactions || {})[r.id]) warn(`reaction ${r.id} has no clip`);
  console.log(`cross-checked ${checked} lines against booth-lines.js + voice-director.js`);
}

console.log(`${path}: ${(m.lines || []).length} lines, ${Object.keys(m.names || {}).length} names, ${Object.keys(m.common || {}).length} common, ${Object.keys(m.reactions || {}).length} reactions, ${Object.keys(m.interjections || {}).length} interjections`);
warns.slice(0, 20).forEach(w => console.log('warn: ' + w));
if (errs.length) { errs.slice(0, 50).forEach(e => console.log('ERROR: ' + e)); console.log(`${errs.length} error(s)`); process.exit(1); }
console.log('manifest OK');
