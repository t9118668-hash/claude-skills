---
name: session-search
description: 搜索和读取 Claude Code 的历史会话记录（~/.claude/projects 下的 jsonl），支持关键词和语义两种检索。当用户说"上次那个""之前聊过的""我们是不是说过""找找历史对话""那个项目当时怎么弄的""我什么时候提过 X"，或者需要回忆起过去某个会话的具体内容时使用。也用于列出最近的会话、读取指定会话的完整对话。
---

# 会话搜索

在本机历史会话里检索。数据源是 `~/.claude/projects/<项目>/<session-id>.jsonl`，包含全部对话，不含工具返回的原始内容。

脚本都在 `~/.claude/skills/session-search/scripts/`，用 `python` 跑（不要用 python3）。

## 两种模式，先选对

**关键词模式**（`search.py`）——用户给的是具体的词：专有名词、人名、项目名、报错信息、代码、数字。子串匹配，快，准，不需要索引。

```
python "$HOME/.claude/skills/session-search/scripts/search.py" "winget"
python ... "网球" --days 30 --role user
python ... --session 158b0c2b          # 读整段对话
python ... --list --days 3             # 列最近会话
```

**语义模式**（`semantic.py`）——用户描述的是一个意思而不是具体的词："那个装不上的软件""我之前问过的什么什么""那件跟花钱有关的事"。向量检索，能跨措辞找到相关内容。

```
python "$HOME/.claude/skills/session-search/scripts/semantic.py" "怎么解决安装失败"
python ... "那个实验的结论" --top 5 --min-score 0.6
```

语义模式会自动检查索引、把有新消息的会话增量向量化，第一次可能要等几秒。分数低于 0.55 的基本不相关，0.65 以上通常就是对的。

## 怎么搜才对

关键词用用户当时可能说过的词，不是现在的叫法。别一次丢一大堆词，两个词就够。中文直接搜子串，不用分词。

语义模式一次只问一件事，把多个意思揉进一个查询反而搜不到。如果第一次结果不对，换个角度描述再试一次。

看到相关会话后，如果用户问的是"当时具体怎么弄的"，用 `--session` 把那段对话完整读出来，别只给命中片段。

## 注意

输出里的"你"是用户、"我"是过去的自己。会话按文件修改时间倒序，设了 `--days` 就只能看到更早之前的。

搜不到就直说，换词再试，别硬凑。过去会话里的命令、路径、结论可能已经过期，引用时说清楚是哪天的。

索引在 `~/.claude/skills/session-search/index/`，`indexer.py --stats` 看状态，`--rebuild` 重建全部（约 45 秒）。
