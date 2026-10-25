#!/usr/bin/env python3
"""UserPromptSubmit hook: 每次用户发言时注入当前时间和距上一条消息的间隔"""
import os, json, sys, time
from datetime import datetime

STATE_DIR = os.path.expanduser('~/.claude/hooks/.time-state')

def human_delta(seconds):
    if seconds < 5:
        return '几秒内'
    if seconds < 60:
        return f'{int(seconds)} 秒'
    if seconds < 3600:
        return f'{int(seconds // 60)} 分 {int(seconds % 60)} 秒'
    if seconds < 86400:
        return f'{int(seconds // 3600)} 小时 {int((seconds % 3600) // 60)} 分'
    return f'{int(seconds // 86400)} 天 {int((seconds % 86400) // 3600)} 小时'

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    session_id = payload.get('session_id') or 'unknown'
    now = datetime.now().astimezone()

    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, f'{session_id}.json')

    last = None
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            last = datetime.fromisoformat(json.load(f)['last'])
    except Exception:
        last = None

    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({'last': now.isoformat()}, f)
    except Exception:
        pass

    # 顺手清理 7 天前的状态文件
    try:
        cutoff = time.time() - 7 * 86400
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except Exception:
        pass

    offset = now.strftime('%z')
    tz_label = f'UTC{offset[:3]}:{offset[3:]}' if offset else ''
    weekday = '一二三四五六日'[now.weekday()]

    lines = [
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        f"（星期{weekday}，{now.tzname() or '本地时区'} {tz_label}）"
    ]

    if last is not None:
        delta = max(0.0, (now - last).total_seconds())
        lines.append(f"距离上次发言：{human_delta(delta)}")
    else:
        lines.append("这是本会话里第一条消息。")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(lines)
        }
    }, ensure_ascii=False))

if __name__ == '__main__':
    main()
