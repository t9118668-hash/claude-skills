#!/usr/bin/env python3
"""为历史会话建向量索引（增量）。

  python indexer.py            增量更新
  python indexer.py --rebuild  清空重建
  python indexer.py --stats    查看状态
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from search import session_files, iter_messages  # noqa: E402

INDEX_DIR = Path(os.path.expanduser('~/.claude/skills/session-search/index'))
FILES_DIR = INDEX_DIR / 'files'
STATE = INDEX_DIR / 'state.json'
MODEL = 'BAAI/bge-small-zh-v1.5'
CHUNK_SIZE = 300
OVERLAP = 50

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')


def chunk_text(text, size=CHUNK_SIZE, overlap=OVERLAP):
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        if i + size >= len(text):
            break
        i += size - overlap
    return out


def file_key(path):
    return hashlib.sha1(str(path).encode('utf-8')).hexdigest()[:16]


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def collect(paths, model, state):
    """对需要更新的文件生成 (chunks, vectors)，返回新 state。"""
    new_state = dict(state)
    batch_chunks, batch_meta, owners = [], [], []

    for path in paths:
        st = path.stat()
        key = file_key(path)
        sig = [int(st.st_mtime), st.st_size]
        if state.get(key, {}).get('sig') == sig and (FILES_DIR / f'{key}.npz').exists():
            continue

        chunks, meta = [], []
        for idx, (role, dt, text) in enumerate(iter_messages(path)):
            for ci, piece in enumerate(chunk_text(text)):
                chunks.append(piece)
                meta.append({
                    'session': path.stem,
                    'project': path.parent.name,
                    'role': role,
                    'ts': dt.isoformat() if dt else None,
                    'idx': idx,
                    'chunk': ci,
                    'text': piece,
                })
        if not chunks:
            new_state[key] = {'sig': sig, 'path': str(path), 'n': 0}
            np.savez_compressed(FILES_DIR / f'{key}.npz', vectors=np.zeros((0, 512), dtype=np.float32), meta=np.array([], dtype=object))
            print(f'  跳过（无内容） {path.parent.name}/{path.stem[:8]}')
            continue

        print(f'  向量化 {path.parent.name}/{path.stem[:8]}  {len(chunks)} 块 …', end='', flush=True)
        t0 = time.time()
        vecs = np.array(list(model.embed(chunks, batch_size=32)), dtype=np.float32)
        np.savez_compressed(FILES_DIR / f'{key}.npz', vectors=vecs, meta=np.array([json.dumps(m, ensure_ascii=False) for m in meta]))
        new_state[key] = {'sig': sig, 'path': str(path), 'n': len(chunks)}
        print(f' {time.time() - t0:.1f}s')

    return new_state


def cmd_stats():
    state = load_state()
    total = sum(v.get('n', 0) for v in state.values())
    print(f'索引文件: {len(state)} 个会话文件, {total} 个块')
    print(f'位置: {INDEX_DIR}')
    if INDEX_DIR.exists():
        size = sum(f.stat().st_size for f in INDEX_DIR.rglob('*') if f.is_file())
        print(f'占用: {size / 1024 / 1024:.1f} MB')


def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    if '--stats' in sys.argv:
        cmd_stats()
        return

    if '--rebuild' in sys.argv:
        for f in FILES_DIR.glob('*.npz'):
            f.unlink()
        if STATE.exists():
            STATE.unlink()
        print('已清空旧索引。')

    from fastembed import TextEmbedding

    state = load_state()
    paths = session_files()
    print(f'检查 {len(paths)} 个会话文件 …')
    t0 = time.time()
    model = TextEmbedding(model_name=MODEL, cache_dir=os.path.expanduser('~/.cache/fastembed'))
    new_state = collect(paths, model, state)

    STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1), encoding='utf-8')
    total = sum(v.get('n', 0) for v in new_state.values())
    print(f'\n完成，用时 {time.time() - t0:.1f}s。索引共 {total} 个块。')


if __name__ == '__main__':
    main()
