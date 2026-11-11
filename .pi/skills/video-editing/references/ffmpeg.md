# ffmpeg 配方集（社群分享向）

> 素材来源：Buzz（GrowthMarketerAgent）的 dtc-ads 管线实践（转场 / 配音 / 导出经验）+ 通用 ffmpeg 用法整理。
> 本机 ffmpeg 6.0（homebrew）。所有命令先拿小样试一遍再跑正式素材。

本项目用 ffmpeg 的场景：截取片段、拼接、压缩、转码兼容、加字幕、截图封面、修音频。
**输出目标永远一致**：mp4 + H.264 + AAC + faststart——微信 / QuickTime / 手机通吃。

## 0. 万能起手式：先查再动

```bash
# 查编码 / 时长 / 分辨率
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height -show_entries format=duration -of compact in.mp4
```

任何处理前先跑一遍：确认源文件是什么（编码、时长、有没有音轨），再决定怎么处理。看内容抽几帧：

```bash
ffmpeg -ss 1 -i in.mp4 -frames:v 1 -vf scale=480:-2 /tmp/preview-1s.jpg
```

## 1. 裁剪片段（最常用）

```bash
# 重编码精确裁剪：从第 8.8 秒到第 13.4 秒
# -ss / -to 放在 -i 前：快速定位 + 默认精确（accurate_seek 会丢弃多余帧）
ffmpeg -ss 8.8 -to 13.4 -i in.mp4 -c:v libx264 -crf 18 -c:a aac -movflags +faststart out.mp4

# 只要前 5 秒（-t = 时长）
ffmpeg -ss 0 -t 5 -i in.mp4 -c:v libx264 -crf 18 -c:a aac -movflags +faststart out.mp4
```

- 精确裁剪**必须重编码视频**（`-c:v libx264`）；想秒完用流复制 `-c copy`，但那会从最近的关键帧开始切、时间点不精确，且拼不齐时更容易出问题——社群分享这种短片一律重编码，几秒钟的事；
- `-ss` 放 `-i` 前是推荐写法（seek 快、默认准确）；放 `-i` 后是纯逐帧解码（慢，一般不需要）；
- 裁剪后如果发现开头黑屏，参考下面第 6 节的「时间戳归零」。

## 2. 拼接多段

```bash
# 前提：各段编码参数一致（分辨率 / 帧率 / 编码都相同）——先各自按第 5 节规范转码
printf "file '%s'\n" /abs/path/a.mp4 /abs/path/b.mp4 > /tmp/concat-list.txt
ffmpeg -f concat -safe 0 -i /tmp/concat-list.txt -c copy out.mp4
```

- 列表文件里写**绝对路径**（用 `'/abs/path'` 单引号包住，避免特殊字符问题）；
- 参数不一致的段：先逐段统一转码（同分辨率 / 帧率 / 编码），再拼；
- 拼接后想加转场（交叉溶解等）用 `xfade` 滤镜（重编码，写法略复杂）——社群分享的短剪一般硬切就够，别贪转场。

## 3. 压缩（微信大小控制）

```bash
# 标准压缩：720p + CRF 23（默认画质档）
ffmpeg -i in.mp4 -vf "scale=-2:720" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart out.mp4

# 只压体积、不改分辨率：调高 CRF（数字越大越小、越糊；18 高质 / 23 默认 / 28 小）
ffmpeg -i in.mp4 -c:v libx264 -crf 28 -preset medium -c:a aac -b:a 96k -movflags +faststart out.mp4
```

- `scale=-2:720` 的 `-2`：宽度自动按比例算、且保证偶数（H.264 要求偶数尺寸）；
- `preset`：`medium` 均衡（默认）；`fast` 更快、文件略大；`slow` 更小更慢；
- 码率参考区间：720p 约 2–4 Mbps、1080p 约 4–8 Mbps（CRF 模式下不用手算码率，这是对照参考）；
- 微信发视频消息会自动压缩，所以**不需要过度追求小体积**——控制在「能发出去」的量级即可，画质留给微信再压一轮。

## 4. 转码兼容（修「播不了 / 没声音」）

```bash
# 保画面、只修音频（典型场景：Opus 装进 mp4 导致微信 / QuickTime 静音）
ffmpeg -i in.mp4 -c:v copy -c:a aac -b:a 192k -movflags +faststart out.mp4

# 全量规范转码（编码不明 / 播不了时的万能修复）
ffmpeg -i in.mp4 -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart out.mp4
```

- `-pix_fmt yuv420p`：强制通用像素格式——很多「电脑能播、手机播不了」是源素材用了 yuv444 / yuv422 这类非通用格式；
- `-movflags +faststart`：把索引挪到文件头——防网络 / 微信里开头黑屏；
- 判断逻辑：画面正常没声音 → 修音频（第一条）；画面也放不出 / 花屏 → 全量转码（第二条）。

## 5. 加字幕

### 硬字幕（烧进画面；推荐——微信里谁都看得见）

```bash
# sub.srt 与命令放同一目录（或写简单路径，避免转义麻烦）、UTF-8 编码
ffmpeg -i in.mp4 -vf "subtitles=sub.srt:force_style='FontName=PingFang SC,FontSize=18,Outline=1,PrimaryColour=&HFFFFFF'" -c:a copy out.mp4
```

- srt 格式（时间格式是毫秒，逗号分隔）：

  ```
  1
  00:00:00,500 --> 00:00:02,800
  第一句字幕

  2
  00:00:02,900 --> 00:00:05,200
  第二句字幕
  ```

- 中文字体用 macOS 自带的 `PingFang SC`（或 Heiti SC）；
- 字号（FontSize）以视频高度的百分之一为感觉基准：720p 用 16–20、1080p 用 22–28，按实际看着调；
- ASS 颜色格式是 `&HAABBGGRR`（注意 BGR 顺序）：白色 `&HFFFFFF`、黑色描边 `&H000000`。

### 软字幕（内嵌轨；微信里不保证显示）

```bash
ffmpeg -i in.mp4 -i sub.srt -c copy -c:s mov_text -metadata:s:s:0 language=chi out.mp4
```

群分享**建议一律硬字幕**（软字幕很多场景看不到）。

## 6. 时间戳归零（防开头黑屏）

多段拼接 / 复杂滤镜处理后，如果出现开头黑屏或时长异常，重编码时加时间戳归零：

```bash
ffmpeg -i in.mp4 -vf "setpts=PTS-STARTPTS" -af "asetpts=PTS-STARTPTS" -c:v libx264 -crf 18 -c:a aac -movflags +faststart out.mp4
```

（无音轨的源去掉 `-af` 部分、加 `-an`。）

## 7. 封面 / 音频 / 音量

```bash
# 截图当封面（发群时配图、视频号封面）
ffmpeg -ss 1 -i in.mp4 -frames:v 1 cover.jpg

# 提取音频
ffmpeg -i in.mp4 -vn -c:a aac -b:a 192k audio.m4a

# 音量太小：增益 6 dB（改音频、画面不动）
ffmpeg -i in.mp4 -af "volume=6dB" -c:v copy out.mp4

# 响度标准化（社媒通用目标 ≈ -14 LUFS）
ffmpeg -i in.mp4 -af "loudnorm=I=-14:TP=-2:LRA=11" -c:v copy out.mp4
```

音量优先用 `loudnorm`（不同来源素材响度不一致时统一）；`volume` 适合「比原声大一点 / 小一点」的微调。

## 8. 倍速与画幅

```bash
# 2 倍速（视频 setpts=0.5*PTS；音频 atempo=2.0——atempo 可写 0.5~2.0）
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" -c:v libx264 -crf 20 -c:a aac out.mp4

# 横屏转竖屏（黑边填充版；要模糊背景填充再说）
ffmpeg -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:a copy out.mp4
```

## 9. 坑清单

1. **Opus-in-mp4 静音坑**（最高频）：下载素材（yt-dlp）或转码时音频选了 Opus，装进 mp4 后微信 / QuickTime / 很多剪辑软件播不出声音——修复就是「保画面、aac 重编码」（第 4 节第一条）；
2. **AV1 编码**：QuickTime 不认——交付文件必须是 H.264；
3. **非 yuv420p 像素格式**：手机播不了的常见原因，全量转码时显式加；
4. **忘加 faststart**：网络 / 微信里开头黑屏或加载慢；
5. **画面比声音短**：部分播放器（微信 / QuickTime）把结尾渲染成黑屏——成品可加 `-shortest` 截齐，或把画面做够时长；
6. **srt 路径含空格 / 中文**：`subtitles=` 滤镜对特殊字符敏感，拷到简单路径（如 `/tmp/sub.srt`）再跑；
7. **循环文件名冲突**：批量脚本输出记得区分文件名（加 `-cut` / `-720p` 等英文后缀），别覆盖源文件。
