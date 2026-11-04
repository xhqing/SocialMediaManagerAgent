---
name: chinese-format-lint
description: 中文 Markdown 稿件的确定性排版检查（13 条规则，附可跑的 Node 脚本，零依赖）。MUST USE 当用户说「检查排版」「排版对不对」「中英空格」「标点规范」「跑一遍 lint」「格式检查」「发之前过一遍格式」「标点用错了没」，或公众号 / 小红书 / 群公告 / README 稿子定稿前要做格式收尾时。把可机械判定的部分从模型判断里剥出来：中英混排空格、省略号、全角数字、全角括号间距、连用感叹号、省略号与「等」重复、千分位逗号、标题层级与跳级、孤立标题、标题带句号、重名标题、句长（默认 40）、文件名规范；5 条支持 --fix 自动修复。NOT for：病句与语法（用 chinese-grammar-proofreader）、去 AI 味（用 lieflat-less-ai-tone）、内容事实核查。
---

# chinese-format-lint — 中文排版确定性检查

排版这套东西有一半是**能算的**，主要是这几件：

- 中英之间要不要空格；
- 省略号写两个字符还是三个半角句点；
- 数字用全角还是半角；
- 标题能不能带句号；
- 四位数以上要不要千分位。

这一半不该交给模型凭感觉。交给脚本，判定可复现、结论能进 CI，改了也不用重跑模型。

## 什么时候用

- 用户说「检查排版」「排版对不对」「中英空格对不对」「标点规范」「跑一遍 lint」「格式检查」「发之前过一遍格式」；
- 公众号 / 小红书 / 群公告 / README 稿子**定稿前**做格式收尾。它跟语法检查、去 AI 味是三条不同的检查线，见下面「边界」；
- 一批 Markdown 需要批量体检，或按规则批量修。

## 怎么跑

脚本在本 skill 目录下，路径相对 skill 根：

```bash
# 报告模式（默认：只报不改）——给 AI 读时加 --no-color，省掉 ANSI 转义
node .claude/skills/chinese-format-lint/scripts/lint.mjs --no-color 文章.md 另一篇.md
```

**路径参数的边界（上游脚本的实际行为，实测）**：参数只接受**文件**，多个文件逐个列；不传参数时才递归扫描当前目录（跳过 `.git`、`node_modules`、`dist`、`build`、`coverage`）。把**目录**当参数传进去会报 `EISDIR`——要扫目录就 `cd` 到那个目录后不带参数跑。

| 选项 | 作用 |
|---|---|
| `--fix` | 自动修 5 条可机械修复的规则（其余仍逐条报） |
| `--strict` | 把 warning 也算作失败（审阅场景） |
| `--no-warnings` | 只看 error，不看写作建议 |
| `--max-sentence-length=N` | 句长阈值，默认 40 |
| `--color` / `--no-color` | 强制开 / 关颜色 |

不传参数时，默认扫描当前目录下所有 Markdown；传了参数就只查列出的文件，不会展开目录。

行内豁免（写进稿子即可）：

```markdown
<!-- lint-disable-next-line sentence-length -->
<!-- lint-disable heading-orphan -->
<!-- lint-enable heading-orphan -->
```

## 规则清单

机械项（`--fix` 能修）：

| 规则 | 查什么 |
|---|---|
| `cn-en-space` | 中文与英文 / 数字之间缺空格 |
| `ellipsis` | 三个半角句点应改中文省略号「……」；单个省略号字符也应补成两个 |
| `fullwidth-digit` | 全角数字应改半角 |
| `fullwidth-paren-spacing` | 全角括号内侧多余空格 |
| `multi-exclaim` | 多个感叹号连用 |

检测项（只报，人工判断）：

| 规则 | 查什么 |
|---|---|
| `ellipsis-with-deng` | 省略号与「等 / 等等」连用（语义重复） |
| `thousand-separator-missing` | 5 位以上数字在金额 / 数量语境里缺千分位逗号（编号、日期、电话不报） |
| `heading-skip-level` | 标题跳级（如 `##` 直接到 `####`） |
| `heading-duplicate-name` | 同级重名标题 |
| `heading-orphan` | 孤立标题（该层级只有一个子标题） |
| `heading-trailing-period` | 标题以句号结尾 |
| `sentence-length` | 单句超阈值（默认 40 个语言单位） |
| `filename-convention` | 文件名应全小写、半角连词线、不含中文 / 下划线 / 空格 |

## 处理流程

1. **先跑报告模式**，把命中按「文件 + 行号 + 规则 + 原文片段」贴给用户，不改文件；
2. **机械项**问一句要不要 `--fix`（用户同意再跑），跑完复跑一次确认残余；
3. **检测项逐条判断**：句长和孤立标题属于「写作建议」。长句不一定该拆，孤立标题也不一定该加，按语义决定，别为了过 lint 硬改；
4. 改完的稿子如果还要过语法检查，顺序是**先内容 → 再语法 → 最后排版**（先排版再改内容会白排一遍）。

## 边界：它查不出什么

- **病句**：搭配不当、语序、成分残缺、指代不明、歧义、逻辑跳跃——这些不在能力范围内，用 `chinese-grammar-proofreader`；
- **AI 腔**：翻译腔、空泛拔高、套话——用 `lieflat-less-ai-tone`；
- **事实与口径**：数字算错、结论外推、来源存疑——脚本不管，靠人核。

一句话：**它保证的是「格式没错」，不是「写得好」。**

## 出处与许可

脚本取自 [fwqaaq/chinese-tech-writing](https://github.com/fwqaaq/chinese-tech-writing) 的 `scripts/lint.mjs`（MIT，Copyright (c) 2026 fwqaaq）。

本项目**只取这一个脚本**，未引入其技术文档写作规范正文——本项目有自己的写作与内容规则。许可全文见同目录 `LICENSE`。
