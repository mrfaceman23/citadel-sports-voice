#!/usr/bin/env python3
"""Citadel Sports voice clip generator (run once on Jordan's PC; re-runs only make new or changed clips).

Reads the booth lines (booth-lines.js through tools/export-lines.mjs, or that script's JSON), renders every spoken
piece with Kokoro, trims and levels it, writes .ogg (Opus 48 kbps mono) and manifest/manifest.json for the Voice
Director in citadel-sports. Needs: Python 3.10+, kokoro, soundfile, numpy; Node (to read booth-lines.js);
ffmpeg for .ogg (without it the clips stay .wav and a warning is printed).

Examples:
  python tools/generate.py --lines ../citadel-sports/App/assets/booth-lines.js          # everything (no player names)
  python tools/generate.py --lines booth-lines.js --only idle                           # just the idle lines
  python tools/generate.py --lines booth-lines.js --names roster.json                   # just player names
  python tools/generate.py --lines booth-lines.js --numbers --teams                     # numbers and team names
  python tools/generate.py --lines booth-lines.js --only vocab                          # flags, members, quarters... (tools/vocab.json)
  python tools/generate.py --lines booth-lines.js --dry-run                             # count only, render nothing

Kokoro has no emotion control. Intensity tiers are pace and volume only (TIERS below): tier 1 (flat) 3% slower,
tier 3 (losing it) 4% faster and 2 dB louder. Note: the Voice Director levels every clip toward one loudness when it
plays and adds its own +/-2 dB per tier, so the baked-in 2 dB mostly matters for players that do not level clips.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

GEN_VERSION = '1'
SR = 24000
VOICES = {  # character: (Kokoro voice, base speed, Kokoro language: b = British, a = American)
    'corvus': ('bm_fable', 0.93, 'b'),
    'bastion': ('am_michael', 1.10, 'a'),
}
TIERS = {1: (0.97, 0.0), 2: (1.00, 0.0), 3: (1.04, 2.0)}  # tier: (speed factor, gain dB)
CARRIER = 'Taylor'                 # neutral word said in place of a fill-in, then cut away
NAME_CARRIER = ('Then', 'again.')  # names and numbers are said inside "Then <x> again." and cut out
SILENCE_DB = -45.0                 # edge trim threshold (dBFS)
TARGET_RMS_DB = -18.0              # active-speech RMS; roughly -16 to -18 LUFS for speech (approximate, no K-weighting)
PEAK_DB = -1.0
PAD_MS = 25                        # silence kept at both edges so the Director's 20 ms crossfade never eats a word
FADE_MS = 5
SLOT_EST_MS = 400                  # duration_ms counts each fill-in as this long (real length depends on the name)
BLANK = 'common/_blank'            # a short silence for punctuation-only pieces ("{score}.")
ACRONYMS = {'NFL', 'AFC', 'NFC', 'TD', 'TDS', 'QB', 'QBS', 'OT', 'MVP', 'ATS', 'RPO', 'YAC', 'I', 'TV', 'OK'}
GROUPS = ['events', 'idle', 'tiers', 'reactions', 'interjections', 'numbers', 'teams', 'vocab', 'names']
COMMON_WORDS = ['yard', 'yards', 'first down', 'touchdown', 'and']


def slug(v):  # same as voice-director.js slug()
    s = str('' if v is None else v).lower().replace('&', 'and')
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', s))


def load_vocab(p):
    """tools/vocab.json -> {set: [text]}. Plain words only (Kokoro pause rule: pacing never comes from punctuation)."""
    v = json.loads(Path(p).read_text(encoding='utf-8'))
    out = {}
    for k, xs in v.items():
        if k.startswith('_'):
            continue
        for t in xs:
            if re.search(r'[.,;:!?\[\]{}*]', t) or not slug(t):
                sys.exit(f'vocab.json {k}: "{t}" must be plain words (no punctuation or marks)')
        out[k] = list(dict.fromkeys(xs))
    return out


def sha(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def tts_text(t):
    """What Kokoro reads: all-caps shouting turned to normal case (else it can spell words letter by letter)."""
    t = re.sub(r'\*[^*]+\*', ' ', t)
    t = re.sub(r"\b[A-Z][A-Z']{1,}\b", lambda m: m.group(0) if m.group(0).replace("'", '') in ACRONYMS else m.group(0).lower(), t)
    return re.sub(r'\s+', ' ', t).strip()


# ---------------------------------------------------------------- engines
class KokoroEngine:
    name = 'kokoro'

    def __init__(self, device=None):
        import torch
        from kokoro import KModel, KPipeline
        repo = 'hexgrad/Kokoro-82M'
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = KModel(repo_id=repo).to(self.device).eval()
        self.pipes = {lc: KPipeline(lang_code=lc, repo_id=repo, model=self.model) for lc in {v[2] for v in VOICES.values()}}
        self.torch = torch

    def synth(self, text, voice, lang, speed):
        """-> (audio float32, tokens [(text, whitespace, start_s, end_s)] or None)"""
        chunks, toks, off = [], [], 0.0
        with self.torch.no_grad():
            for r in self.pipes[lang](text, voice=voice, speed=speed, split_pattern=None):
                if r.audio is None:
                    continue
                a = r.audio.detach().cpu().numpy().astype(np.float32)
                for t in (r.tokens or []):
                    st, en = getattr(t, 'start_ts', None), getattr(t, 'end_ts', None)
                    toks.append((t.text, t.whitespace, None if st is None else st + off, None if en is None else en + off))
                chunks.append(a)
                off += len(a) / SR
        audio = np.concatenate(chunks) if chunks else np.zeros(1, np.float32)
        return audio, (toks if toks and any(t[2] is not None for t in toks) else None)


class OnnxEngine:
    """kokoro-onnx with the same Kokoro v1.0 voices. No word timings, so carriers are cut by silence search.
    Only for testing where the PyTorch weights cannot be downloaded."""
    name = 'kokoro-onnx'

    def __init__(self, folder):
        from kokoro_onnx import Kokoro
        self.k = Kokoro(str(Path(folder) / 'kokoro-v1.0.onnx'), str(Path(folder) / 'voices-v1.0.bin'))

    def synth(self, text, voice, lang, speed):
        a, sr = self.k.create(text, voice=voice, speed=speed, lang='en-gb' if lang == 'b' else 'en-us')
        assert sr == SR
        return np.asarray(a, np.float32), None


# ---------------------------------------------------------------- audio helpers
def rms_curve(x, win=240, hop=60):
    """frame RMS (10 ms window, 2.5 ms hop) -> (centres, rms)"""
    if len(x) < win:
        return np.array([len(x) // 2]), np.array([np.sqrt(np.mean(x ** 2)) if len(x) else 0.0])
    cs = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    starts = np.arange(0, len(x) - win + 1, hop)
    return starts + win // 2, np.sqrt((cs[starts + win] - cs[starts]) / win)


def quietest(x, lo_s, hi_s):
    """sample index of the quietest 10 ms between lo_s and hi_s seconds"""
    lo, hi = max(0, int(lo_s * SR)), min(len(x), int(hi_s * SR))
    if hi - lo < 300:
        return int(np.clip((lo + hi) // 2, 0, len(x)))
    c, r = rms_curve(x[lo:hi])
    return lo + int(c[int(np.argmin(r))])


_MEL = {}


def logmel(x, n_fft=512, hop=240, bands=40):
    if n_fft not in _MEL:  # triangular mel filters, 60 Hz to 7.6 kHz
        mel = lambda f: 2595 * np.log10(1 + f / 700)
        hz = lambda m: 700 * (10 ** (m / 2595) - 1)
        pts = hz(np.linspace(mel(60), mel(7600), bands + 2))
        bins = np.floor((n_fft + 1) * pts / SR).astype(int)
        fb = np.zeros((bands, n_fft // 2 + 1))
        for i in range(bands):
            l, c, r = bins[i], bins[i + 1], max(bins[i + 2], bins[i + 1] + 1)
            fb[i, l:c] = (np.arange(l, c) - l) / max(1, c - l)
            fb[i, c:r] = (r - np.arange(c, r)) / max(1, r - c)
        _MEL[n_fft] = (fb, np.hanning(n_fft))
    fb, win = _MEL[n_fft]
    x = np.concatenate([x, np.zeros(n_fft, np.float32)])
    frames = np.stack([x[i:i + n_fft] * win for i in range(0, len(x) - n_fft, hop)])
    f = np.log(fb @ (np.abs(np.fft.rfft(frames, axis=1)) ** 2).T + 1e-8).T
    f -= f.mean(axis=1, keepdims=True)
    return f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-8)


def dtw_edge(full, part):
    """seconds into `full` where `part` (the same words said alone, both trimmed) ends: open-end DTW"""
    A, B = logmel(part), logmel(full)
    n, m = len(A), len(B)
    if n < 3 or m < 3:
        return len(part) / SR
    cost = 1 - A @ B.T
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    j = np.arange(1, m + 1)
    lo, hi = max(1, int(n * 0.35)), min(m, int(n * 1.6) + 1)
    score = D[n, 1:] / (n + j)
    score[:lo - 1] = np.inf
    score[hi:] = np.inf
    return (int(np.argmin(score)) + 1) * 240 / SR


def trim(x):
    thr = 10 ** (SILENCE_DB / 20)
    c, r = rms_curve(x)
    on = np.where(r > thr)[0]
    if not len(on):
        return x[:0]
    a = max(0, c[on[0]] - int(0.015 * SR) - 120)
    b = min(len(x), c[on[-1]] + int(0.030 * SR) + 120)
    return x[a:b]


def finish(x, gain_db):
    x = trim(x)
    if not len(x):
        return np.zeros(int(PAD_MS * 2 / 1000 * SR), np.float32)
    thr = 10 ** (SILENCE_DB / 20)
    _, r = rms_curve(x)
    act = r[r > thr]
    cur = float(np.sqrt(np.mean(act ** 2))) if len(act) else float(np.sqrt(np.mean(x ** 2)) or 1e-4)
    g = 10 ** ((TARGET_RMS_DB + gain_db) / 20) / max(cur, 1e-6)
    peak = float(np.max(np.abs(x))) or 1e-6
    g = min(g, 10 ** ((PEAK_DB if gain_db <= 0 else -0.5) / 20) / peak)
    x = (x * g).astype(np.float32)
    n = int(FADE_MS / 1000 * SR)
    if len(x) > 2 * n:
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    pad = np.zeros(int(PAD_MS / 1000 * SR), np.float32)
    return np.concatenate([pad, x, pad])


class Renderer:
    def __init__(self, engine):
        self.e = engine
        self.ctx_cache = {}
        self.audio_s = 0.0
        self.calls = 0
        self.fallbacks = 0

    def say(self, text, character, speed):
        voice, _, lang = VOICES[character]
        self.calls += 1
        a, toks = self.e.synth(text, voice, lang, speed)
        self.audio_s += len(a) / SR
        return a, toks

    def ctx_audio(self, ctx, character, speed):
        """a carrier said on its own (trimmed); used when the engine gives no word timings"""
        k = (ctx, character, speed)
        if k not in self.ctx_cache:
            self.ctx_cache[k] = trim(self.say(ctx, character, speed)[0])
        return self.ctx_cache[k]

    def render(self, core, character, speed, left='', right=''):
        """say `core` inside optional carriers and return only the core, cut at the carrier boundaries"""
        core_t = tts_text(core)
        sep = '' if (not left or re.match(r"^[.,!?;:']", core_t)) else ' '
        full = (left + sep + core_t + ((' ' + right) if right else '')).strip()
        a, toks = self.say(full, character, speed)
        if not left and not right:
            return a
        s0, s1 = (len(left) + len(sep)) if left else 0, (len(left) + len(sep) + len(core_t)) if right else len(full)
        lo, hi = 0, len(a)
        rebuilt = ''.join(t[0] + t[1] for t in toks).strip() if toks else ''
        if toks and abs(len(rebuilt) - len(full)) <= 2:  # word timings from Kokoro: cut between carrier and core
            offs, o = [], 0
            for t in toks:
                offs.append(o)
                o += len(t[0]) + len(t[1])
            if left:
                cut = None
                for (tx, _, st, en), of in zip(toks, offs):
                    if st is None:
                        continue
                    if of < s0 < of + len(tx) and core_t.startswith("'"):  # "{team}'s": keep the 's at the carrier's end
                        cut = max(st, en - 0.09); break
                    if of >= s0:
                        cut = st; break
                if cut is not None:
                    lo = quietest(a, cut - 0.04, cut + 0.04)
            if right:
                cut = next((st for (tx, _, st, en), of in zip(toks, offs) if st is not None and of >= s1 and re.search(r'\w', tx)), None)
                if cut is not None:
                    hi = quietest(a, cut - 0.04, cut + 0.04)
        else:  # no word timings: line the carrier said on its own up against the sentence (DTW) to find its edge
            a = trim(a)
            lo, hi = 0, len(a)
            if left:
                c = self.ctx_audio(left + ("'s" if core_t.startswith("'s") else ''), character, speed)
                b = dtw_edge(a, c) - (0.09 if core_t.startswith("'s") else 0)
                lo = quietest(a, b - 0.03, b + 0.03)
            if right:
                c = self.ctx_audio(right, character, speed)
                b = len(a) / SR - dtw_edge(a[::-1].copy(), c[::-1].copy())
                hi = quietest(a, b - 0.03, b + 0.03)
            if hi <= lo:
                lo, hi = 0, len(a)
        cut = a[lo:hi]
        # sanity check against the same words said on their own: a cut far off in length means the carrier edge
        # was missed, so the plain (carrier-free) take is used instead and counted in the summary
        alone = trim(self.say(core_t, character, speed)[0])
        r = len(trim(cut)) / max(1, len(alone))
        if not (0.45 <= r <= 1.5):
            self.fallbacks += 1
            return alone
        return cut


# ---------------------------------------------------------------- plan
def segments(pieces):
    """voice-director.js segments(): text runs (an *action* does not split them), fill-ins, pauses, overlap point"""
    segs, ov = [], None
    for p in pieces:
        last = segs[-1] if segs else None
        if p.get('text') is not None:
            if last and last['kind'] == 'text' and not last.get('closed'):
                last['text'] += ' ' + p['text']
            else:
                segs.append({'kind': 'text', 'text': p['text']})
        elif p.get('slot'):
            if last: last['closed'] = True
            segs.append({'kind': 'slot', 'slot': p['slot']})
        elif p.get('pause') is not None:
            if last: last['closed'] = True
            segs.append({'kind': 'pause', 'ms': int(p['pause'])})
        elif p.get('overlap'):
            ov = len(segs)
            if last: last['closed'] = True
    return segs, ov


def is_blank(t):
    return not re.search(r'[A-Za-z0-9]', t)


def file_stub(line_id, who):
    return re.sub(r'[^a-z0-9_]+', '_', line_id.lower().replace(':' + who + ':', ':')).strip('_')


def plan_line(L):
    who, tier = L['character'], int(L.get('intensity') or 2)
    voice, base, _ = VOICES[who]
    spd, gdb = round(base * TIERS[tier][0], 4), TIERS[tier][1]
    segs, ov = segments(L['pieces'])
    stub, pieces, pauses, jobs, pending, n, ov_piece = file_stub(L['id'], who), [], [], [], 0, 0, None
    for j, s in enumerate(segs):
        if j == ov:
            ov_piece = len(pieces)
        if s['kind'] == 'pause':
            pending += s['ms']
            continue
        if pieces:
            pauses.append(pending)
        pending = 0
        if s['kind'] == 'slot':
            pieces.append({'slot': s['slot']})
            continue
        n += 1
        if is_blank(s['text']):
            pieces.append({'file': BLANK, 'text': s['text']})
            continue
        prev, nxt = (segs[j - 1] if j else None), (segs[j + 1] if j + 1 < len(segs) else None)
        left = CARRIER if prev and prev['kind'] == 'slot' else ''
        right = ''
        # split mid-sentence by the [overlap] mark (no pause): the real neighbouring words are the carrier
        if prev and prev['kind'] == 'text':
            left = ' '.join(tts_text(prev['text']).split()[-2:])
        if nxt and nxt['kind'] == 'text':
            right = ' '.join(tts_text(nxt['text']).split()[:2])
        if nxt and nxt['kind'] == 'slot':
            after = segs[j + 2] if j + 2 < len(segs) else None
            punct = re.match(r'^[.,!?;:]+', after['text']).group(0) if after and after['kind'] == 'text' and re.match(r'^[.,!?;:]', after['text']) else ''
            right = CARRIER + punct
        path = f'lines/{who}/{stub}__{n:02d}'
        h = sha(GEN_VERSION, left, s['text'], right, voice, spd, gdb)
        pieces.append({'file': path, 'text': s['text']})
        jobs.append({'path': path, 'character': who, 'text': s['text'], 'left': left, 'right': right, 'speed': spd, 'gain': gdb, 'sha': h})
    if ov is not None and ov_piece is None:
        ov_piece = len(pieces)
    entry = {'id': L['id'], 'character': who, 'text': L['raw'], 'trigger': L.get('trigger'), 'group': L.get('group'),
             'pieces': pieces, 'pauses': pauses, 'intensity': tier}
    if ov_piece is not None:
        entry['overlap_piece'] = ov_piece
    return entry, jobs


def plan_simple(path, who, text, tier=2, left='', right=''):
    voice, base, _ = VOICES[who]
    spd, gdb = round(base * TIERS[tier][0], 4), TIERS[tier][1]
    return {'path': path, 'character': who, 'text': text, 'left': left, 'right': right, 'speed': spd, 'gain': gdb,
            'sha': sha(GEN_VERSION, left, text, right, voice, spd, gdb)}


# ---------------------------------------------------------------- main
def load_lines(p):
    p = Path(p)
    if p.suffix.lower() == '.json':
        return json.loads(p.read_text(encoding='utf-8'))
    exp = Path(__file__).with_name('export-lines.mjs')
    out = subprocess.run(['node', str(exp), str(p)], capture_output=True, text=True, encoding='utf-8')
    if out.returncode:
        sys.exit('could not read booth-lines.js with Node:\n' + out.stderr)
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser(description='Citadel Sports voice clip generator')
    ap.add_argument('--lines', required=True, help='path to booth-lines.js, or the JSON from export-lines.mjs')
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parent.parent), help='citadel-sports-voice folder')
    ap.add_argument('--only', default='', help='comma list: ' + ', '.join(GROUPS) + ', or trigger names (td, idle_weather...)')
    ap.add_argument('--names', metavar='ROSTER.json', help='render player names from [{id, name, team}]')
    ap.add_argument('--numbers', action='store_true', help='render 0-99 and yard / yards / first down / touchdown / and')
    ap.add_argument('--teams', action='store_true', help='render the 32 team cities and nicknames')
    ap.add_argument('--vocab', metavar='VOCAB.json', default=str(Path(__file__).with_name('vocab.json')),
                    help='fill-in words (flags, members, quarters, ordinals...) for the vocab group; default tools/vocab.json')
    ap.add_argument('--limit', type=int, default=0, help='only the first N lines (testing)')
    ap.add_argument('--numbers-max', type=int, default=99, help=argparse.SUPPRESS)
    ap.add_argument('--engine', choices=['kokoro', 'onnx'], default='kokoro')
    ap.add_argument('--onnx-dir', help='folder with kokoro-v1.0.onnx and voices-v1.0.bin (engine onnx)')
    ap.add_argument('--device', help='cuda or cpu (default: cuda when available)')
    ap.add_argument('--base', default='../', help='manifest "base" (clip paths are relative to the repo root; "../" = one up from manifest/)')
    ap.add_argument('--no-prune', action='store_true', help='keep clips whose line no longer exists')
    ap.add_argument('--dry-run', action='store_true', help='count what would be made; render nothing')
    a = ap.parse_args()

    repo = Path(a.repo)
    data = load_lines(a.lines)
    only = [x.strip() for x in a.only.split(',') if x.strip()]
    picked = set(only)
    if a.names: picked.add('names')
    if a.numbers: picked.add('numbers')
    if a.teams: picked.add('teams')
    full_run = not picked and not a.limit
    if not picked:
        # a -Limit listen test makes only the first N lines, not every reaction, number and team as well
        picked = {'events', 'idle', 'tiers'} if a.limit else set(GROUPS) - {'names'}
    triggers = {x for x in picked if x not in GROUPS}

    def chosen(L):
        return L['group'] in picked or L['trigger'] in triggers

    # ---- the plan: every manifest entry and every clip job
    entries, jobs, names_map, common_map, react_map, inter_map, sel_ids = [], [], {}, {}, {}, {}, set()
    vocab_map, vocab_counts = {}, {}
    lines = data['lines'][:a.limit] if a.limit else data['lines']
    for L in lines:
        e, js = plan_line(L)
        if chosen(L):
            sel_ids.add(e['id'])
            jobs += js
        entries.append(e)
    if 'reactions' in picked:
        for r in data.get('reactions', []):
            p = f"reactions/{r['character']}/{r['id']}"
            jobs.append(plan_simple(p, r['character'], r.get('tts') or r.get('text', ''), int(r.get('intensity') or 2)))
            react_map[r['id']] = p
    if 'interjections' in picked:
        for x in data.get('interjections', []):
            p = f"interjections/{x['character']}/{x['id']}"
            jobs.append(plan_simple(p, x['character'], x['text']))
            inter_map[x['id']] = p
    # names, numbers and teams: one clip per voice. Map key "<slug>@<character>" (the Director looks that up first),
    # file <folder>/<stem>_c (Corvus) or _b (Bastion)
    def shared(folder, stem, key, text, left=NAME_CARRIER[0], right=NAME_CARRIER[1], target=common_map):
        for who in VOICES:
            p = f'{folder}/{stem}_{who[0]}'
            jobs.append(plan_simple(p, who, text, 2, left, right))
            target.setdefault(f'{key}@{who}', p)
    if 'numbers' in picked:
        for i in range(0, a.numbers_max + 1):
            shared('common', f'num_{i}', str(i), str(i))
        for w in COMMON_WORDS:
            shared('common', 'word_' + slug(w).replace('-', '_'), slug(w), w)
    if 'teams' in picked:
        for t in data.get('teams', []):
            c = t['code'].lower()
            if slug(t['city']) + '@corvus' not in common_map:
                shared('common', f'team_{c}_city', slug(t['city']), t['city'])
            shared('common', f'team_{c}_nick', slug('the ' + t['nick']), 'the ' + t['nick'])
    if 'vocab' in picked:  # vocab/<set>_<word>_c|b, key = slug (the Director looks in names, then vocab, then common)
        for name, words in load_vocab(a.vocab).items():
            vocab_counts[name] = len(words)
            for w in words:
                k = slug(w)
                if f'{k}@corvus' in vocab_map:
                    continue
                shared('vocab', f"{name}_{k.replace('-', '_')}", k, w, target=vocab_map)
    if 'names' in picked:
        if not a.names:
            sys.exit('--only names needs --names roster.json')
        for r in json.loads(Path(a.names).read_text(encoding='utf-8')):
            k = slug(r['name'])
            if not k or f'{k}@corvus' in names_map:
                continue
            shared('names', k.replace('-', '_'), k, r['name'], target=names_map)

    # ---- previous run: hashes per clip, and the old manifest for anything this run does not touch
    man_path, hash_path = repo / 'manifest' / 'manifest.json', repo / 'manifest' / 'hashes.json'
    old = json.loads(man_path.read_text(encoding='utf-8')) if man_path.exists() else {}
    hashes = json.loads(hash_path.read_text(encoding='utf-8')) if hash_path.exists() else {}
    by_sha = {v['sha']: k for k, v in hashes.items()}
    have_ffmpeg = shutil.which('ffmpeg') is not None
    ext = '.ogg' if have_ffmpeg else '.wav'

    def existing(stem):
        for x in ('.ogg', '.wav'):
            if (repo / (stem + x)).exists():
                return stem + x
        return None

    todo, reuse, skip = [], [], 0
    seen = set()
    for j in jobs:
        if j['path'] in seen:
            continue
        seen.add(j['path'])
        h, cur = hashes.get(j['path']), existing(j['path'])
        if h and h['sha'] == j['sha'] and cur:
            skip += 1
        elif j['sha'] in by_sha and existing(by_sha[j['sha']]):
            reuse.append(j)
        else:
            todo.append(j)
    est_words = sum(len((j['left'] + ' ' + j['text'] + ' ' + j['right']).split()) for j in todo)
    print(f'plan: {len(seen)} clips ({skip} unchanged, {len(reuse)} copied from identical text, {len(todo)} to render, ~{est_words} words)')
    by_folder = {}
    for j in todo + reuse:
        f = j['path'].split('/')[0]
        by_folder[f] = by_folder.get(f, 0) + 1
    if by_folder:
        print('new clips by folder: ' + ', '.join(f'{k} {v}' for k, v in sorted(by_folder.items())))
    if vocab_counts:
        print('vocab sets (words, x2 voices): ' + ', '.join(f'{k} {v}' for k, v in vocab_counts.items()) + f' = {len(vocab_map)} clips')
    if 'names' in picked:
        print(f'names: {len(names_map) // 2} players = {len(names_map)} clips')
    if a.dry_run:
        return
    if not have_ffmpeg:
        print('WARNING: ffmpeg not found, clips are written as .wav (bigger, and .gitignore keeps .wav out of git). Install ffmpeg and re-run.')

    eng = None
    if todo:
        eng = OnnxEngine(a.onnx_dir) if a.engine == 'onnx' else KokoroEngine(a.device)
        print(f'engine: {eng.name}' + (f' on {eng.device}' if hasattr(eng, "device") else ''))
    R = Renderer(eng) if eng else None
    wav_dir = repo / 'tmp' / 'wav'
    t0 = time.time()

    def write(stem, audio):
        if have_ffmpeg:
            w = wav_dir / (stem + '.wav')
            w.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(w), audio, SR, subtype='PCM_16')
            out = repo / (stem + '.ogg')
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(w), '-ac', '1', '-c:a', 'libopus', '-b:a', '48k',
                            '-vbr', 'on', '-application', 'audio', str(out)], check=True)
            stale = repo / (stem + '.wav')
            if stale.exists(): stale.unlink()
        else:
            out = repo / (stem + '.wav')
            out.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out), audio, SR, subtype='PCM_16')

    blank = np.zeros(int(0.06 * SR), np.float32)
    if not existing(BLANK) or (hashes.get(BLANK, {}).get('sha') != 'blank60'):
        write(BLANK, blank)
    hashes[BLANK] = {'sha': 'blank60', 'ms': 60}

    for j in reuse:
        src = existing(by_sha[j['sha']])
        dst = j['path'] + Path(src).suffix
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / src, repo / dst)
        hashes[j['path']] = dict(hashes[by_sha[j['sha']]])
    copied = 0
    for i, j in enumerate(todo, 1):
        twin = by_sha.get(j['sha'])
        if twin and existing(twin):  # same text, voice and speed made earlier in this run
            src = existing(twin)
            shutil.copyfile(repo / src, repo / (j['path'] + Path(src).suffix))
            hashes[j['path']] = dict(hashes[twin])
            copied += 1
            continue
        a_ = R.render(j['text'], j['character'], j['speed'], j['left'], j['right'])
        a_ = finish(a_, j['gain'])
        write(j['path'], a_)
        hashes[j['path']] = {'sha': j['sha'], 'ms': int(round(len(a_) / SR * 1000))}
        by_sha[j['sha']] = j['path']
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f'  {i}/{len(todo)} clips, {el:.0f}s so far, about {el / i * (len(todo) - i):.0f}s left', flush=True)

    # ---- manifest
    ms = lambda p: hashes.get(p, {}).get('ms')
    built = {}
    for e in entries:
        if e['id'] not in sel_ids:
            continue
        dur, ok = 0, True
        for k, p in enumerate(e['pieces']):
            if 'file' in p:
                m = ms(p['file'])
                if m is None: ok = False; m = 0
                f = existing(p['file'])
                p['file'] = f or (p['file'] + ext)
                p['sha'] = hashes.get(p['file'].rsplit('.', 1)[0], {}).get('sha')
                p['ms'] = m
                dur += m
            else:
                dur += SLOT_EST_MS
        dur += sum(e['pauses'])
        e['duration_ms'] = dur
        if 'overlap_piece' in e:
            k = e['overlap_piece']
            e['overlap_ms'] = sum(p.get('ms', SLOT_EST_MS) for p in e['pieces'][:k]) + sum(e['pauses'][:k])
        e['sha'] = sha(*[p.get('sha') or p.get('slot') for p in e['pieces']], e['pauses'])
        if ok:
            built[e['id']] = e
    old_lines = {x['id']: x for x in old.get('lines', [])}
    out_lines = []
    for e in entries:
        if e['id'] in built:
            out_lines.append(built[e['id']])
        elif e['id'] in old_lines and not full_run:
            out_lines.append(old_lines[e['id']])
    if not full_run:  # keep entries this run did not plan (e.g. --limit)
        planned = {e['id'] for e in entries}
        out_lines += [x for i, x in old_lines.items() if i not in planned]

    def with_ext(mp):
        return {k: (existing(v) or v + ext) for k, v in mp.items()}
    keep = lambda name, new: new if full_run else {**old.get(name, {}), **new}
    manifest = {
        'version': 1, 'generator': f'citadel-sports-voice tools/generate.py v{GEN_VERSION}', 'engine': eng.name if eng else old.get('engine', 'kokoro'),
        'base': a.base, 'voices': {k: {'voice': v[0], 'speed': v[1]} for k, v in VOICES.items()},
        'tiers': {str(k): {'speed': v[0], 'gain_db': v[1]} for k, v in TIERS.items()},
        'slot_estimate_ms': SLOT_EST_MS,
        'lines': out_lines,
        'names': {**old.get('names', {}), **with_ext(names_map)},  # names only come from -Names runs: never dropped by a full run
        'common': keep('common', with_ext(common_map)),
        'vocab': keep('vocab', with_ext(vocab_map)),
        'reactions': keep('reactions', with_ext(react_map)), 'interjections': keep('interjections', with_ext(inter_map)),
    }
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')

    pruned = 0
    if full_run and not a.no_prune:  # only clips this generator made and that nothing points to any more
        live = {j['path'] for j in jobs} | {BLANK}
        for stem in [k for k in hashes if k not in live and not k.startswith('names/')]:  # a full run never makes names
            for x in ('.ogg', '.wav'):
                f = repo / (stem + x)
                if f.exists(): f.unlink(); pruned += 1
            del hashes[stem]
    hash_path.write_text(json.dumps(dict(sorted(hashes.items())), indent=0) + '\n', encoding='utf-8')

    el = time.time() - t0
    rtf = f', {R.audio_s / el:.1f}x realtime' if R and el > 0 else ''
    fb = f' {R.fallbacks} fill-in pieces used a plain take (carrier cut looked wrong).' if R and R.fallbacks else ''
    summary = (f'Voice clips: {len(todo) - copied} rendered, {len(reuse) + copied} copied, {skip} unchanged, {pruned} removed.{fb} '
               f'Manifest: {len(out_lines)} lines, {len(manifest["names"])} names, {len(manifest["common"])} common, {len(manifest["vocab"])} vocab, '
               f'{len(manifest["reactions"])} reactions, {len(manifest["interjections"])} interjections. Took {el:.0f}s{rtf}.')
    print(summary)
    (repo / 'tmp').mkdir(exist_ok=True)
    (repo / 'tmp' / 'last-summary.txt').write_text(summary + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
