---
name: time-context
description: 让 Claude Code 每次收到你的消息时都知道当前具体时间、星期、时区和距上次发言过了多久。当用户问"现在几点""我们聊了多久""你知不知道今天周几"，或者任务本身对时间敏感（定时、跨天整理、记录时间线）时使用。安装需要通过 UserPromptSubmit hook 注入，不能只装 skill。
---

# 时间感知

给模型补上它本来没有的东西：现在几点。

大语言模型没有时钟。它知道今天日期（Claude Code 会在环境信息里给），但不知道当前时刻，也不知道你上一句话是几秒前还是三小时前说的。这个 skill 用 `UserPromptSubmit` hook 在每次用户发言时注入一行上下文，模型就能回答"我们聊了多久"这类问题，也能在长会话里判断时间跨度。

## 安装

1. 把这个脚本放到 `~/.claude/hooks/time-context.py`。
2. 在 `~/.claude/settings.json` 的 `hooks` 里加：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"$HOME/.claude/hooks/time-context.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

3. 重启 Claude Code（或打开一次 `/hooks` 让配置重载）。

只放 SKILL.md 不生效——真正的注入靠 hook。

## 效果

每次发言，模型会在输入旁边收到：

```
当前时间：2026-10-25 12:48:32（星期日，中国标准时间 UTC+08:00）
距离上次发言：2 分 23 秒
```

间隔按大小自动换单位：5 秒内是"几秒内"，一分钟内报秒，一小时内报分秒，一天内报小时分，更久报天数。

## 实现细节

状态按 `session_id` 存在 `~/.claude/hooks/.time-state/<session_id>.json`，每次触发时读旧值、写新值，顺手清掉 7 天前的文件。时区取系统本地时区，输出里带 `UTC+08:00` 这种偏移。

脚本不依赖第三方包，只用标准库。

## 注意

hook 每次发消息都会跑一次 Python 进程，Windows 上大概几十毫秒，可以接受。如果你觉得吵，可以改成只在间隔超过一定时长时才输出。

`UserPromptSubmit` 的 stdout 会作为上下文注入，所以脚本里除了那行 JSON 什么都不要 print，否则会污染上下文。
