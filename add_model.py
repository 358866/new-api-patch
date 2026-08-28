#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NewAPI 加模型一键脚本
用法：
  python add_model.py "model-name"                 # 加到最后一个渠道
  python add_model.py "model-name" --channel 8      # 加到指定渠道
  python add_model.py "model-name" --all            # 加到所有渠道
  python add_model.py "m1" "m2" --all               # 一次加多个模型
  python add_model.py --list                        # 列出渠道和模型
"""
import argparse
import json
import sqlite3
import subprocess

DB = r'F:\AI Manger\NewApi\data\one-api.db'


def get_conn():
    conn = sqlite3.connect(DB)
    return conn


def list_channels(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT id, name, type, base_url, models FROM channels ORDER BY id').fetchall()
    for r in rows:
        models = r['models'].split(',') if r['models'] else []
        print(f"#{r['id']} [{r['name']}] type={r['type']} base={r['base_url']}")
        print(f"    models({len(models)}): {', '.join(models)}")
    conn.row_factory = None


def add_models_to_channel(conn, channel_id, models):
    cur = conn.cursor()
    row = cur.execute('SELECT models FROM channels WHERE id=?', (channel_id,)).fetchone()
    if not row:
        print(f'ERROR: channel #{channel_id} not found')
        return False
    existing = row[0].split(',') if row[0] else []
    added = []
    for m in models:
        m = m.strip()
        if not m:
            continue
        if m in existing:
            print(f'  already exists: {m}')
            continue
        existing.append(m)
        added.append(m)
    if not added:
        return False
    cur.execute('UPDATE channels SET models=? WHERE id=?', (','.join(existing), channel_id))
    print(f'channel #{channel_id}: added {len(added)} models')
    return True


def update_ratio(conn, models):
    cur = conn.cursor()
    row = cur.execute("SELECT value FROM options WHERE key='ModelRatio'").fetchone()
    ratio = json.loads(row[0]) if row else {}
    for m in models:
        ratio[m] = 0
    cur.execute('INSERT OR REPLACE INTO options (key, value) VALUES (?, ?)',
                ('ModelRatio', json.dumps(ratio, ensure_ascii=False)))
    print(f'ModelRatio: {len(models)} models set to 0 (free)')


def rebuild_abilities(conn):
    cur = conn.cursor()
    cur.execute('DELETE FROM abilities')
    channels = cur.execute('SELECT id, weight, models FROM channels').fetchall()
    n = 0
    for cid, weight, models in channels:
        for m in models.split(',') if models else []:
            m = m.strip()
            if not m:
                continue
            cur.execute('INSERT INTO abilities ("group", model, channel_id, enabled, priority, weight) VALUES (?,?,?,1,0,?)',
                        ('default', m, cid, weight))
            n += 1
    print(f'abilities rebuilt: {n} rows')


def restart_newapi():
    r = subprocess.run(['docker', 'restart', 'new-api'], capture_output=True, text=True)
    if r.returncode == 0:
        print('NewAPI restarted')
    else:
        print('WARN: docker restart failed (is it running?), run manually: docker restart new-api')
        print(r.stderr)


def main():
    parser = argparse.ArgumentParser(description='NewAPI add model script')
    parser.add_argument('models', nargs='*', help='model names to add')
    parser.add_argument('--channel', type=int, help='channel id to add to')
    parser.add_argument('--all', action='store_true', help='add to all channels')
    parser.add_argument('--list', action='store_true', help='list channels and models')
    parser.add_argument('--no-restart', action='store_true', help='skip container restart')
    args = parser.parse_args()

    conn = get_conn()
    if args.list:
        list_channels(conn)
        conn.close()
        return

    if not args.models:
        parser.print_help()
        conn.close()
        return

    if args.all:
        channels = [r[0] for r in conn.execute('SELECT id FROM channels').fetchall()]
    elif args.channel:
        channels = [args.channel]
    else:
        channels = [conn.execute('SELECT MAX(id) FROM channels').fetchone()[0]]
    print(f'target channels: {channels}')

    models = [m.strip() for m in args.models if m.strip()]
    print(f'models to add: {models}')

    changed = False
    for cid in channels:
        if add_models_to_channel(conn, cid, models):
            changed = True
    update_ratio(conn, models)
    rebuild_abilities(conn)
    conn.commit()
    conn.close()

    if changed and not args.no_restart:
        restart_newapi()
    print('done')


if __name__ == '__main__':
    main()
