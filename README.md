# claude-skills

两个给 Claude Code 用的 skill，补上模型本来缺的两样东西：**现在几点**，和**以前说过什么**。

## 里面有什么

### time-context — 时间感知

Claude 知道今天日期，不知道此刻几点，也不知道你上一句话是几秒前还是三小时前说的。这个 skill 用 `UserPromptSubmit` hook 在每次发言时注入一行：

```
当前时间：2026-10-25 12:48:32（星期日，中国标准时间 UTC+08:00）
距离上次发言：2 分 23 秒
```

安装：把 `hooks/time-context.py` 复制到 `~/.claude/hooks/`，在 `settings.json` 里挂上 hook，重启。详细步骤见 [skills/time-context/SKILL.md](skills/time-context/SKILL.md)。

不依赖任何第三方包。

### session-search — 会话搜索

在 `~/.claude/projects/` 的历史 jsonl 里检索，两种模式：

- **关键词**：子串匹配，几十毫秒。"winget"、"1017"、"那个报错" 里的具体词。
- **语义**：向量检索，你说的是一句意思而不是一个词也能找到。本地跑 `BAAI/bge-small-zh-v1.5`（512 维 ONNX），中文识别很好，不用联网。

```
python scripts/search.py "winget" --days 30
python scripts/semantic.py "怎么解决安装失败" --top 5
python scripts/search.py --session 158b0c2b     # 读整段对话
python scripts/search.py --list --days 3        # 列最近会话
```

索引会自动增量更新——有新消息的会话在下次语义搜索前先补向量，不用手动跑。

安装：

```bash
pip install fastembed
mkdir -p ~/.claude/skills/session-search
cp -r skills/session-search/* ~/.claude/skills/session-search/
python ~/.claude/skills/session-search/scripts/indexer.py   # 首次建索引
```

首次建索引约 45 秒（1400 条消息 / 3300 个块 / 6.5 MB）。模型从 HuggingFace 下载，国内可以设 `HF_ENDPOINT=https://hf-mirror.com`。

## 为什么不用现成的

市面上的会话搜索插件大多依赖某个特定 agent 的运行时（cordis、LangChain、MCP server），换一个客户端就用不了。这两个只依赖文件系统和你自己的 jsonl，谁的机器上都能跑。

## 许可

MIT
