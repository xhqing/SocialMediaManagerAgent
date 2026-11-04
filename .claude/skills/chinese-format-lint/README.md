# chinese-format-lint

中文 Markdown 稿件的**确定性排版检查**。用途是把「空格、标点、全角半角、标题层级、句长、文件名」这类能算的规则交给脚本，不让模型凭感觉判。

## 来源

脚本 `scripts/lint.mjs` 取自 [fwqaaq/chinese-tech-writing](https://github.com/fwqaaq/chinese-tech-writing)（MIT，Copyright (c) 2026 fwqaaq）。

本项目**只取这个脚本**，没有引入它的《中文技术文档写作规范》正文与 SKILL.md。技术文档文风那套规范跟本项目的公众号 / 小红书内容不是一回事；本项目的内容规则另有 `CLAUDE.md` 与 `social-media` skill 管。

## 用法

```bash
# 报告模式（只报不改）
node .claude/skills/chinese-format-lint/scripts/lint.mjs --no-color 文章.md

# 自动修机械项
node .claude/skills/chinese-format-lint/scripts/lint.mjs --fix 文章.md
```

13 条规则、各项阈值的说明与处理流程见 `SKILL.md`。

## 环境

Node.js ≥ 18，只用 `node:fs` / `node:path` 标准库，无第三方依赖、无需 `npm install`。

## 边界

查排版，不查语法。病句用 `chinese-grammar-proofreader`，去 AI 味用 `lieflat-less-ai-tone`。

## 许可

MIT，全文见 `LICENSE`（保留上游版权声明）。
