---
name: video-editing
description: >
  MUST USE when 处理任何视频剪辑相关的事：剪视频 / 视频剪辑 / 剪个片段 / 截取片段 / 剪短 / 从视频里剪出某一段 /
  把讲 XX 那段剪出来 / 视频拼接 / 视频加字幕 / 配字幕 / 视频压缩 / 视频太大发不出去 / 视频转码 / 格式转换 /
  微信里播不了 / 视频没声音 / 音频修复 / 视频加封面 / 提取音频 / 调音量 / 用 ChatCut / AI 剪视频 /
  把长视频剪成短视频发群里 / 视频素材处理 / 录屏处理 / 帮我处理一下这个视频。
  两条路线：ffmpeg（本地精确：裁剪 / 拼接 / 压缩 / 转码 / 字幕 / 封面 / 修复）与 ChatCut（mcporter 直连，
  自然语言语义剪辑 / 自动转写字幕 / 精修导出，本机已装好）。
  覆盖微信分享规格（H.264+AAC / faststart / 大小控制）与成品验收清单。
  NOT for：视频下载本身（用 yt-dlp，本文顺带指路）；DTC 广告投流视频（GrowthMarketerAgent 的 dtc-ads）；
  纯文字内容处理。
---

# 视频剪辑（社群分享）

运营工作中要动手处理视频时的总入口。目标：把素材剪成**能在微信群里正常播放、群友看着舒服**的成片。

两条路线：

- **ffmpeg**（本地、精确、批量、零成本）——默认主力，剪时间点、拼接、压缩、转码、加字幕都靠它；
- **ChatCut**（AI 语义剪辑、自动字幕）——适合「用一句话说清楚要剪什么」的单条精修（如「把讲 AI 变现那段剪出来」），本机已通过 mcporter 接好。

## 什么时候用

- 「剪一下这个视频」「剪个片段」「剪成 30 秒」「把讲 XX 那段剪出来」
- 「给视频加字幕」
- 「视频太大发不出去」「压缩一下」「转成 mp4」「微信里播不了 / 没声音」
- 「用 ChatCut 剪」「AI 剪视频」
- 处理素材：下载的视频、录屏、别人发来的片子

不适用：

- 下载视频素材本身——用 `yt-dlp`（关键注意点见文末「素材下载」）；
- DTC 广告投流视频——那是 GrowthMarketerAgent（Buzz）的 dtc-ads 领域。

## 第一步：先明确交付规格

剪之前先想清楚三件事（用户没说就按默认来，不反复追问）：

1. **给谁看 / 干什么用**——群内分享？发给老板发布？探路样片？
2. **多长**——群内分享 15~60 秒最好（太长的群友不会看完）；完整素材复现另说；
3. **画幅**——手机拍的素材竖屏 9:16 为主；横屏 16:9 另说。

输出的硬规格（微信能否正常播放取决于这个）：

- 容器 / 编码：**mp4 + H.264 视频 + AAC 音频**——微信、QuickTime、各种手机通吃的唯一稳妥组合；
- **不要** AV1 / Opus 等新编码（历史坑：Opus 装进 mp4 后微信、QuickTime 里全部静音，画面还在、声音没了）；
- 加 `-movflags +faststart`，拼接 / 裁剪后时间戳归零（各段 `setpts` / `asetpts`）——防微信里开头黑屏；
- 分辨率：720p / 1080p（竖屏 720×1280 / 1080×1920）；
- 大小：微信发视频消息会自动压缩，超过客户端提示的限制就改用「文件」方式发送（以微信实际提示为准）；
- **画面时长 ≥ 声音时长**，尾部留 0.1 秒左右余量——画面比声音短时，微信 / QuickTime 会把结尾渲染成黑屏。

## 两条路线怎么选

| 场景 | 路线 | 说明 |
|---|---|---|
| 裁剪时间点 / 截取片段 | ffmpeg | 精确、可批量；流复制秒级完成或重编码 |
| 拼接多段 / 压缩 / 转码 | ffmpeg | 参数完全可控 |
| 加固定文案字幕 | ffmpeg | 烧录进画面，谁打开都能看到 |
| 识别人声自动转字幕 | ChatCut | 英文实测好；**中文先拿一条试**（未实测） |
| 「把讲 XX 那段剪出来」 | ChatCut | 语义剪辑（按说话内容剪），ffmpeg 做不到 |
| 截图封面 / 提取音频 / 调音量 | ffmpeg | |
| MG 动效 / AI 配乐 | ChatCut | 耗积分（免费层不含） |
| 批量处理一堆文件 | ffmpeg | 写循环脚本 |

一句话：**帧级精确、批量、零成本 → ffmpeg；语义理解、按说话内容剪 → ChatCut**。

## 通用纪律

1. **先看素材再动手**：用 `ffprobe` 查编码 / 时长 / 分辨率，抽几帧看内容，别盲剪；
2. **不覆盖源文件**：一切处理输出到新文件（如 `xxx-cut.mp4`），原素材原样保留；
3. **产出实际打开看**：交付前用 QuickTime 实际播放确认（画面 + 声音 + 时长），不以命令成功返回为准；
4. **版本可回溯**：成片多版本用英文后缀区分（`-v2`、`-final`），旧版本不删除；
5. **临时文件放 `tmp/`**（确认在 `.gitignore` 里），成片交给用户时再定去向。

## ffmpeg 速查（完整配方见 references/ffmpeg.md）

```bash
# 查：编码 / 时长 / 分辨率（任何操作前先跑一遍）
ffprobe -v error -show_entries stream=codec_type,codec_name -show_entries format=duration -of compact in.mp4

# 裁：从第 8.8 秒到第 13.4 秒（重编码，精确）
ffmpeg -ss 8.8 -to 13.4 -i in.mp4 -c:v libx264 -crf 18 -c:a aac -movflags +faststart out.mp4

# 压：压到 720p、默认质量（CRF 23）
ffmpeg -i in.mp4 -vf "scale=-2:720" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart out.mp4

# 转：只修音频不改画面（如 Opus 静音修复）
ffmpeg -i in.mp4 -c:v copy -c:a aac -b:a 192k -movflags +faststart out.mp4

# 截：取第 1 秒画面当封面
ffmpeg -ss 1 -i in.mp4 -frames:v 1 cover.png
```

拼接、字幕、音量、拼接后时间戳处理等更多配方见 `references/ffmpeg.md`。

## ChatCut 工作流（完整参考见 references/chatcut.md）

ChatCut（chatcut.io）是「用自然语言剪视频」的 AI 编辑器。本机已配置好两种入口：

- **mcporter 直连**（推荐，可自动化）：`mcporter call chatcut.<工具名> --args '{...}'`；
- **Claude Code 插件**（人在环里时）：已装 `chatcut@chatcut-inc`，开新会话直接说「用 ChatCut 帮我……」即可。

**免费层边界**（2026-10-04 实测，单日单账户观察）：建项目 / 导入素材 / 时间线编辑 / 自动转写 / 导出 **不计积分**（纯剪辑够用）；MG 动效 / AI 音乐 / 音色克隆 / 视频生成等增值功能要积分或订阅。

八步工作流（概览）：

1. **连通性**：`mcporter list chatcut` 现取工具清单（工具数会漂，别背名单）；
2. **项目**：`list_projects` 看现有 / `create_project` 新建 / `target_project` 切换；
3. **导入本机素材**：起本机文件服务（serve-local-media）→ `import_media`（批量 `files` 形式，1–16 个/批）；目标项目要在本机浏览器里开着；
4. **编辑**：改时间线用 `manage_timelines` + `edit_item`（先 `validateOnly:true` 干跑）；**按说话内容剪**用 `read_script` → 编辑 timeline.md → `apply_script`；
5. **字幕**：导入即自动转写；`read_captions` 读、`edit_captions` 改（样式 / 翻译 / 双语）；
6. **预览**：`preview_timeline` 出帧图核对（改一眼看一次，别闷头剪）；
7. **导出**：`submit_export`（无人值守用 `renderMode:"cloud"`）→ `track_export` 取下载链接；
8. **验收**：下载后用 `ffprobe` 验证（注意实测坑：ChatCut 导出产物音频比画面长 0.05s，交付前修剪对齐）。

## 成品验收清单

- [ ] `ffprobe` 确认：视频轨 H.264、音频轨 AAC（或 `-an` 无音轨）、时长符合预期
- [ ] QuickTime 实际播放：画面正常、声音正常、无黑屏 / 静音 / 卡顿
- [ ] 画面 ≥ 声音时长；尾部无黑屏（被截断）
- [ ] 分辨率 / 画幅符合场景；文件大小合理（微信发得出去）
- [ ] （有字幕时）字幕与语音对齐、无错别字、位置不挡关键内容
- [ ] 文件名用英文、语义清晰
- [ ] 原素材与旧版本未删除

## 素材下载（顺带）

需要从网上下载视频素材时用 `yt-dlp`。一条最重要的纪律（实证踩坑）：

**下载时选 H.264 视频 + AAC 音频**——YouTube 上默认可能选中 AV1 + Opus，`--merge-output-format mp4` 只换容器不重编码，Opus 音轨装进 mp4 后微信 / QuickTime 播不了或静音：

```bash
yt-dlp -S "res:720,vcodec:h264,acodec:aac" --merge-output-format mp4 -o "tmp/%(id)s.%(ext)s" "<视频URL>"
```

下完照例 `ffprobe` 验证；已下坏的（Opus 版）用上面「转」的命令重编码音频即可修复。
