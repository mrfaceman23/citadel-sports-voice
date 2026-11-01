#!/usr/bin/env python3
"""Make roster.json (the player names to record) from Jordan's Sleeper leagues. Python stdlib only, public Sleeper API, no login.

  python tools/sleeper-roster.py                      # leagues from tools/leagues.local.json -> tmp/roster.json
  python tools/sleeper-roster.py --all-active         # also every active QB/RB/WR/TE/K on an NFL team (any game's scorer)

tools/leagues.local.json (Jordan fills it in; .gitignore keeps it off GitHub):
  { "leagues": ["<Sleeper league id>", "<second league id>"], "extra": ["Tucker Kraft"], "trending": 25 }
  - leagues: the number at the end of the league's web address (sleeper.com/leagues/<id>/...)
  - extra: any other names the booth should be able to say (the week's notable players)
  - trending: also take the N most-added players on Sleeper in the last 24 hours (0 = none)
Output: [{ "id": "<sleeper id>", "name": "Josh Jacobs", "team": "GB" }], the format generate.py --names reads.
The full Sleeper player list (~5 MB) is cached in tmp/ for a day (Sleeper asks callers to fetch it at most once a day).
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

API = 'https://api.sleeper.app/v1'
SKILL = {'QB', 'RB', 'WR', 'TE', 'K'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'citadel-sports-voice'}), timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description='roster.json from Sleeper leagues')
    ap.add_argument('--config', default=str(here / 'leagues.local.json'))
    ap.add_argument('--out', default=str(here.parent / 'tmp' / 'roster.json'))
    ap.add_argument('--all-active', action='store_true', help='also every active QB/RB/WR/TE/K on an NFL team')
    a = ap.parse_args()

    cfg_path = Path(a.config)
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps({'leagues': [], 'extra': [], 'trending': 25}, indent=1) + '\n', encoding='utf-8')
        sys.exit(f'Made {cfg_path}: put your two Sleeper league ids in "leagues" and run this again.')
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))

    cache = here.parent / 'tmp' / 'sleeper-players.json'
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        players = json.loads(cache.read_text(encoding='utf-8'))
    else:
        players = get(f'{API}/players/nfl')
        cache.write_text(json.dumps(players), encoding='utf-8')

    ids, why = [], {}
    def add(pid, reason):
        if pid not in why:
            ids.append(pid); why[pid] = reason
    for lg in cfg.get('leagues', []):
        rosters = get(f'{API}/league/{lg}/rosters')
        n = 0
        for r in rosters:
            for pid in (r.get('players') or []) + (r.get('reserve') or []) + (r.get('taxi') or []):
                add(str(pid), 'league'); n += 1
        print(f'league {lg}: {len(rosters)} teams, {n} rostered players')
    if int(cfg.get('trending') or 0) > 0:
        for t in get(f"{API}/players/nfl/trending/add?lookback_hours=24&limit={int(cfg['trending'])}"):
            add(str(t['player_id']), 'trending')
    if a.all_active:
        for pid, p in players.items():
            if p.get('active') and p.get('team') and p.get('position') in SKILL:
                add(pid, 'active')

    out, seen = [], set()
    for pid in ids:
        p = players.get(pid) or {}
        name = p.get('full_name') or ' '.join(x for x in (p.get('first_name'), p.get('last_name')) if x)
        if not name or p.get('position') == 'DEF' or name.lower() in seen:  # team defenses are said as the team
            continue
        seen.add(name.lower())
        out.append({'id': pid, 'name': name, 'team': p.get('team') or ''})
    for name in cfg.get('extra', []):
        if name.lower() not in seen:
            seen.add(name.lower()); out.append({'id': 'extra', 'name': name, 'team': ''})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'roster: {len(out)} players -> {a.out} (each becomes 2 clips, one per voice)')


if __name__ == '__main__':
    main()
