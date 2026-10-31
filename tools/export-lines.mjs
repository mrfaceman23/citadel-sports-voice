// export-lines.mjs: turn citadel-sports App/assets/booth-lines.js into the JSON the generator reads.
// Usage: node tools/export-lines.mjs <path to booth-lines.js> [out.json]   (no out = print to stdout)
// Only reads the file's exports (lines, tiers, reactions, interjections, TEAMS, speechPieces, stripMarks).
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { writeFileSync } from 'node:fs';

const src = process.argv[2];
if (!src) { console.error('usage: node tools/export-lines.mjs <booth-lines.js> [out.json]'); process.exit(2); }
const B = createRequire(import.meta.url)(resolve(src));
if (typeof B.speechPieces !== 'function' || !B.tiers) {
  console.error('This booth-lines.js has no speechPieces()/tiers: it is older than v9.3.2 (booth-lines-speech). Use a branch that has the speech-ready lines.');
  process.exit(3);
}
const idle = new Set(B.idleTriggers || []);
const out = { source: 'booth-lines.js', line_count: 0, lines: [], reactions: [], interjections: [], teams: [] };

function add(id, character, trigger, group, intensity, raw) {
  out.lines.push({ id, character, trigger, group, intensity, raw, text: B.stripMarks(raw), pieces: B.speechPieces(raw) });
}
// plain pools: booth key trigger:who:index (what say() returns as .key)
for (const t of B.triggers) for (const who of Object.keys(B.lines[t])) B.lines[t][who].forEach((l, i) => add(`${t}:${who}:${i}`, who, t, idle.has(t) ? 'idle' : 'events', 2, l));
// intensity tiers: trigger:who:tN:index
for (const t of Object.keys(B.tiers || {})) for (const who of Object.keys(B.tiers[t])) for (const n of Object.keys(B.tiers[t][who]))
  B.tiers[t][who][n].forEach((l, i) => add(`${t}:${who}:t${n}:${i}`, who, t, 'tiers', Number(n), l));
for (const who of Object.keys(B.reactions || {})) for (const r of B.reactions[who]) out.reactions.push({ ...r, character: who });
for (const who of Object.keys(B.interjections || {})) for (const kind of ['overlap', 'listening'])
  for (const x of (B.interjections[who][kind] || [])) out.interjections.push({ ...x, kind, character: who });
for (const [code, [city, nick]] of Object.entries(B.TEAMS || {})) out.teams.push({ code, city, nick });
out.line_count = out.lines.length;

const json = JSON.stringify(out, null, 1);
if (process.argv[3]) { writeFileSync(process.argv[3], json); console.error(`export-lines: ${out.lines.length} lines, ${out.reactions.length} reactions, ${out.interjections.length} interjections, ${out.teams.length} teams -> ${process.argv[3]}`); }
else process.stdout.write(json);
