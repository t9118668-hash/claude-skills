#!/usr/bin/env python3
"""语义搜索历史会话（需要先用 indexer.py 建索引）。

  python semantic.py "怎么修网盘的问题"
  python semantic.py "那次实验" --top 10 --days 7
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

INDEX_DIR = Path(os.path.expanduser('~/.claude/skills/session-search/index'))
FILES_DIR = INDEX_DIR / 'files'
MODEL = 'BAAI/bge-small-zh-v1.5'

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def load_index():
    vecs, metas = [], []
    if not FILES_DIR.exists():
        return None, None
    for f in FILES_DIR.glob('*.npz'):
        try:
            data = np.load(f, allow_pickle=True)
        except Exception:
            continue
        v = data['vectors']
        m = data['meta']
        if v.shape[0] == 0:
            continue
        vecs.append(v)
        for raw in m:
            metas.append(json.loads(str(raw)))
    if not vecs:
        return None, None
    return np.vstack(vecs), metas


def stale_files():
    """返回索引到期（新增或有改动）的会话文件。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from indexer import load_state, file_key, session_files
    state = load_state()
    out = []
    for p in session_files():
        st = p.stat()
        if state.get(file_key(p), {}).get('sig') != [int(st.st_mtime), st.st_size]:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description='语义搜索历史会话')
    ap.add_argument('query', nargs='+')
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--days', type=int)
    ap.add_argument('--role', choices=['user', 'assistant', 'all'], default='all')
    ap.add_argument('--min-score', type=float, default=0.55)
    ap.add_argument('--width', type=int, default=200)
    ap.add_argument('--no-update', action='store_true', help='不自动更新索引')
    args = ap.parse_args()

    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=MODEL, cache_dir=os.path.expanduser('~/.cache/fastembed'))

    if not args.no_update:
        pending = stale_files()
        if pending:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from indexer import collect, load_state
            print(f'索引更新：{len(pending)} 个会话有变动 …', file=sys.stderr)
            state = load_state()
            new_state = collect(pending, model, state)
            from indexer import STATE
            STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1), encoding='utf-8')

    vecs, metas = load_index()
    if vecs is None:
        print('索引是空的，先运行：python ~/.claude/skills/session-search/scripts/indexer.py')
        return

    q = np.array(list(model.query_embed([' '.join(args.query)]))[0], dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)

    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    scores = (vecs / norms) @ q

    cutoff = None
    if args.days:
        cutoff = datetime.now().astimezone() - timedelta(days=args.days)

    order = np.argsort(-scores)
    seen = set()
    shown = 0
    for i in order:
        s = float(scores[i])
        if s < args.min_score or shown >= args.top:
            break
        m = metas[i]
        if args.role != 'all' and m['role'] != args.role:
            continue
        if cutoff and m.get('ts'):
            try:
                if datetime.fromisoformat(m['ts']) < cutoff:
                    continue
            except Exception:
                pass
        key = (m['session'], m['idx'])
        if key in seen:
            continue
        seen.add(key)

        stamp = '??'
        if m.get('ts'):
            try:
                stamp = datetime.fromisoformat(m['ts']).astimezone().strftime('%Y-%m-%d %H:%M')
            except Exception:
                pass
        who = '你' if m['role'] == 'user' else '我'
        print(f"[{s:.2f}] {stamp} · {who} · 会话 {m['session'][:8]}")
        print(f"  {m.get('text', '')[:args.width]}")
        print()
        shown += 1

    if shown == 0:
        print('没有足够相关的片段，换个说法试试，或者用关键词模式。')


if __name__ == '__main__':
    main()
