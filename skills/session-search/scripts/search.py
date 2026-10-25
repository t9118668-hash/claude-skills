#!/usr/bin/env python3
"""搜索 Claude Code 历史会话记录（~/.claude/projects/*/*.jsonl）。

用法:
  python search.py "关键词"                    全文搜索
  python search.py "关键词" --role user --days 7
  python search.py --session <session-id>      输出某次会话的对话
  python search.py --list --days 3             列出最近的会话
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECTS = Path(os.path.expanduser('~/.claude/projects'))


def local_dt(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()
    except Exception:
        return None


def clean(text):
    """去掉 hook 注入的系统内容，只留真实对话。"""
    s = text.lstrip()
    if s.startswith('<command-name>'):
        import re
        m = re.search(r'<command-name>(.*?)</command-name>', s)
        name = m.group(1).strip() if m else '?'
        ma = re.search(r'<command-args>(.*?)</command-args>', s, re.S)
        extra = f' {ma.group(1).strip()[:60]}' if ma and ma.group(1).strip() else ''
        return f'[命令 {name}{extra}]'
    markers = ('<system-reminder>', 'UserPromptSubmit hook additional context',
               'SessionStart hook additional context', '<local-command')
    if s.startswith(markers):
        return ''
    return text


def iter_messages(path):
    """yield (role, dt, text)"""
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            role = d.get('type')
            if role not in ('user', 'assistant') or d.get('isSidechain'):
                continue
            msg = d.get('message') or {}
            content = msg.get('content')
            text = ''
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = '\n'.join(
                    c.get('text', '') for c in content
                    if isinstance(c, dict) and c.get('type') == 'text'
                )
            text = clean(text).strip()
            if not text:
                continue
            yield role, local_dt(d.get('timestamp')), text


def session_files():
    return sorted(PROJECTS.glob('*/*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)


def snippet(text, terms, width=160):
    """围绕第一个命中词截一段。"""
    low = text.lower()
    pos = -1
    for t in terms:
        pos = low.find(t)
        if pos >= 0:
            break
    if pos < 0:
        pos = 0
    start = max(0, pos - width // 3)
    piece = text[start:start + width].replace('\n', ' ')
    return ('…' if start > 0 else '') + piece + ('…' if start + width < len(text) else '')


def cmd_search(args):
    terms = [t.lower() for t in args.query]
    cutoff = None
    if args.days:
        from datetime import timedelta
        cutoff = datetime.now().astimezone() - timedelta(days=args.days)

    hits = 0
    scanned = 0
    for path in session_files():
        sid = path.stem
        project = path.parent.name
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        except Exception:
            mtime = None
        if cutoff and mtime and mtime < cutoff:
            break  # 文件按 mtime 倒序，后面的都更旧

        file_hits = []
        for role, dt, text in iter_messages(path):
            if cutoff and dt and dt < cutoff:
                continue
            if args.role != 'all' and role != args.role:
                continue
            low = text.lower()
            if all(t in low for t in terms):
                file_hits.append((dt, role, text))
        scanned += 1

        if file_hits:
            print(f"\n=== 会话 {sid[:8]} | {project} | {mtime:%Y-%m-%d %H:%M} | {len(file_hits)} 条命中 ===")
            shown = file_hits[-args.per_session:]
            for dt, role, text in shown:
                stamp = dt.strftime('%m-%d %H:%M') if dt else '??'
                who = '你' if role == 'user' else '我'
                print(f"[{stamp}] {who}: {snippet(text, terms, args.width)}")
            hits += len(file_hits)
            if len(file_hits) > len(shown):
                print(f"  （另有 {len(file_hits) - len(shown)} 条更早的未显示）")

        if args.limit and hits >= args.limit * 5:
            break

    if hits == 0:
        print(f"没有找到包含 {' 且 '.join(args.query)} 的会话（扫描了 {scanned} 个会话文件）。")
    else:
        print(f"\n共 {hits} 条命中，扫描了 {scanned} 个会话文件。")


def cmd_session(args):
    target = args.session
    for path in session_files():
        if path.stem.startswith(target) or path.parent.name.startswith(target):
            print(f"# 会话 {path.stem}\n# 项目 {path.parent.name}\n")
            n = 0
            for role, dt, text in iter_messages(path):
                stamp = dt.strftime('%Y-%m-%d %H:%M') if dt else '??'
                who = '你' if role == 'user' else '我'
                body = text if len(text) <= args.width else text[:args.width] + '…'
                print(f"[{stamp}] {who}: {body}\n")
                n += 1
                if args.limit and n >= args.limit:
                    print(f"…（已截断，显示 {n} 条）")
                    return
            if n == 0:
                print("（这个会话里没有可读的对话内容，可能只是开了个头就关了。）")
            return
    print(f"没找到会话 {target}")


def cmd_list(args):
    from datetime import timedelta
    cutoff = datetime.now().astimezone() - timedelta(days=args.days) if args.days else None
    for path in session_files():
        mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        if cutoff and mtime < cutoff:
            continue
        first = ''
        count = 0
        for role, dt, text in iter_messages(path):
            if role == 'user':
                first = text.replace('\n', ' ')[:70]
                break
            count += 1
        print(f"[{mtime:%Y-%m-%d %H:%M}] {path.stem[:8]}  {path.parent.name[:40]}\n    开头: {first or '(空)'}")


def main():
    ap = argparse.ArgumentParser(description='搜索 Claude Code 历史会话')
    ap.add_argument('query', nargs='*', help='关键词，多个词之间是 AND 关系')
    ap.add_argument('--role', choices=['user', 'assistant', 'all'], default='all')
    ap.add_argument('--days', type=int, help='只看最近 N 天')
    ap.add_argument('--limit', type=int, default=50, help='最多命中的大致上限')
    ap.add_argument('--per-session', type=int, default=5, help='每个会话最多显示几条')
    ap.add_argument('--width', type=int, default=160, help='每条显示宽度')
    ap.add_argument('--session', help='输出指定会话的全文（可用 ID 前缀）')
    ap.add_argument('--list', action='store_true', help='列出最近的会话')
    args = ap.parse_args()

    if args.list:
        cmd_list(args)
    elif args.session:
        cmd_session(args)
    elif args.query:
        cmd_search(args)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
