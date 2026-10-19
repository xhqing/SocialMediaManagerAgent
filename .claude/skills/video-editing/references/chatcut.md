# ChatCut 完整参考

> **实测依据**：Buzz（GrowthMarketerAgent）2026-10-04 免费层全流程实测（T1–T5：建项目 / 导入 / 时间线 / 转写 / 导出，全不计积分）+ 2026-10-09 复核；
> Gatsby 2026-10-09 现场核对本机链路——`list_projects` / `create_project` / `read_project` / `delete_project`
> 实调通过（测试项目已清理）、`serve-local-media` 本机服务实跑正常、工具清单现取 61 个。
> **「文件导入到编辑器、语义剪辑效果、导出成品」三个环节本轮未重跑**（导入要求浏览器开着目标项目），
> 沿用 Buzz 的实测结论。
> 工具参数以 `mcporter list chatcut` 现取为准——本文写作时是 61 个工具（2026-10-09），工具数会漂。

ChatCut（chatcut.io）是一个「用自然语言剪视频」的 AI 视频编辑器。对本项目最有价值的四件事：

1. **语义剪辑**——按说话内容剪（「把讲 AI 变现那段剪出来」），ffmpeg 做不到；
2. **自动转写字幕**——导入视频自动转写，可生成 / 编辑字幕；
3. **单条精修**——时间线、淡入淡出、转场、裁剪，用自然语言描述即可；
4. **云端导出**——渲染在云端完成，无人值守也能出片。

两项边界要记住：

- **成片交付层仍以 ffmpeg 为主**——帧级精确、可脚本重放、零成本；ChatCut 适合「单条、语义、人看得见」的处理，不适合当批量管线；
- **免费层边界**（2026-10-04 实测，单日单账户观察）：建项目 / 导入 / 时间线编辑 / 转写 / 导出 **全不计积分**；MG 动效 / AI 音乐 / 音色克隆 / 数字人 / 视频生成 / 翻译等增值功能要积分或订阅。

---

## 一、连接与凭证（本机已就绪）

本机两种入口都已装好：

| 入口 | 状态 | 适用 |
|---|---|---|
| **mcporter 直连 MCP**（推荐，可自动化） | v0.9.0 已装；配置 `~/.mcporter/mcporter.json`；凭证 `~/.mcporter/credentials.json`（OAuth，带 refresh_token、自动刷新） | 我在 pi 里全自动驱动 |
| **Claude Code 插件** | `chatcut@chatcut-inc` v1.10.15 已装已授权（`claude mcp get plugin:chatcut:chatcut` 显示 ✔ Connected） | 人在环里操作、想看画面 |

### 命令模板

```bash
# 现取工具清单（带完整参数文档）——先看再用，别背名单
mcporter list chatcut

# 调任意工具
mcporter call chatcut.<工具名> --args '{...参数...}'
```

注意事项：

- **别在仓库目录里跑 `mcporter config add`**——它默认把配置写到当前目录的 `config/`，会污染项目；本机配置已在 `~/.mcporter/` 就位，不需要再配。
- **OAuth 授权进程必须挂 tmux**（如遇凭证失效需要重新授权时）：pi 的 bash 工具会回收后台进程，`nohup &` 也不够——用 `tmux new-session -d` 挂起才是可靠做法。
- 如果调用卡在授权提示：`mcporter auth chatcut`（浏览器批一次即可，账号已记住同意时通常无感）。

### 插件自带 18 个技能（人环操作时的操作手册）

路径：`~/.claude/plugins/cache/chatcut-inc/chatcut/1.10.15/skills/`

覆盖：asset-import（导入）/ export（导出）/ transcription（转写）/ create-motion-graphics / music / video-gen / voice / video-translation / verification（验证）/ known-errors（已知问题）等。用 Claude Code 插件干活前，对应环节先读它。

---

## 二、八步工作流

### 第 1 步：连通性确认

```bash
mcporter list chatcut             # 能返回工具清单 = 链路通
mcporter call chatcut.list_projects --args '{}'   # 能返回项目列表 = 凭证有效
```

### 第 2 步：项目（建 / 选 / 切）

```bash
# 看现有项目（拿 projectId）
mcporter call chatcut.list_projects --args '{}'

# 新建（不传尺寸默认 1920×1080 / 30fps；竖屏项目传 1080×1920）
mcporter call chatcut.create_project --args '{"name":"群分享-短剪","compositionWidth":1080,"compositionHeight":1920,"fps":30}'

# 切到某个项目（后续调用不带 projectId 时默认操作它）
mcporter call chatcut.target_project --args '{"projectId":"<pid>"}'
```

要点：`create_project` 会返回 `editorUrl`——**要给人看的时候把链接给出去**（用户能在浏览器里打开、看到编辑器里的实际画面）。

### 第 3 步：导入本机素材（关键步骤）

ChatCut 在云端，「导入本机文件」靠插件自带的**本机文件服务** + `import_media` 两步完成：

```bash
# 1) 把要导入的文件起一个临时的本机 HTTP 服务（tmux 挂起）
#    会话名务必用 `pi-` 前缀（如 pi-chatcut-import）——pi 的 session-guard 只允许 agent
#    自行清理 pi- 前缀的后台会话；用别的名字之后就清不掉了（会被守卫拦截）。
S=~/.claude/plugins/cache/chatcut-inc/chatcut/1.10.15/skills/asset-import/scripts/serve-local-media.mjs
tmux new-session -d -s pi-chatcut-import "node $S --port 43991 --ttl 3600 --origin https://app.chatcut.io /abs/path/a.mp4 /abs/path/b.mp4"
sleep 1
tmux capture-pane -p -t pi-chatcut-import | tail -3   # ← 打印一行现成的 JSON（imports 数组：assetId/url/filename/sizeBytes）

# 2) 把打印的 imports 数组内容喂给 import_media（批量；1–16 个/批）
mcporter call chatcut.import_media --args '{"action":"from_editor","files":[...],"projectId":"<pid>"}'

# 3) 导完关掉文件服务
tmux kill-session -t pi-chatcut-import
```

前置条件与细节：

- **目标项目必须在同一台机器的浏览器里开着**（编辑器页面挂在后台也行）——导入走的是「浏览器 ↔ 本机服务」的 loopback 通道，编辑器不在环境里就不通；
- `files` 数组里**每一项是一段 JSON 字符串**（不是对象数组）：`{"assetId":"<自己生成的 UUID 或脚本给的>","url":"<本机服务地址>","filename":"a.mp4","sizeBytes":12345}`；
- 批量最多 **16 个/批**（并发 8 个）；返回有序结果，每项含 `assetId / filename / ok / status 或 error`；**部分成功会保留**，失败项用**同一个 assetId** 重试；
- 单个文件也可以走顶层字段形式（`assetId` / `url` / `filename` / `sizeBytes`），但批量更省事；
- 成功状态是 `locally_imported`（本机字节已持久化、素材已注册）；云端上传 / 转写可能还在后台（大视频会延后到需要云端字节时），需要时用 `browse_assets` 查；
- 没有同机编辑器时的兜底：`action="create_session"` 走上传通道（插件 helper 一次最多 4 个文件）。

### 第 4 步：编辑

#### 4a. 时间线编辑（物理剪辑）

用于：把素材放到轨道上、裁剪、拼接、加淡入淡出 / 转场、调位置。

```bash
# 看时间线结构（轨道、条目、时长、帧号）
mcporter call chatcut.manage_timelines --args '{"action":"list","projectId":"<pid>"}'
# 建轨道（如 9:16 竖屏时间线）
mcporter call chatcut.manage_timelines --args '{"action":"create","projectId":"<pid>"}'

# 放素材上轨道（先 validateOnly 干跑，再提交）
mcporter call chatcut.edit_item --args '{"adds":["{\"type\":\"video\",\"assetId\":\"<aid>\",\"from\":\"0s\",\"duration\":\"8s\",\"trackId\":\"V1\",\"sourceStartFromInSeconds\":8.8}"],"validateOnly":true,"projectId":"<pid>"}'
```

**`edit_item` 是本参考里最容易踩坑的工具**，必须记住：

- `adds` / `updates` / `deletes` 是「**JSON 字符串数组**」——每一项是字符串形式的 JSON，不是对象数组。手写转义容易错，推荐用 `jq` 组装：

  ```bash
  # 把一条 add 写进临时文件，再用 jq 包成字符串数组
  cat > /tmp/add1.json <<'EOF'
  {"type":"video","assetId":"<aid>","from":"0s","duration":"8s","trackId":"V1"}
  EOF
  ARGS=$(jq -n --rawfile a /tmp/add1.json '{adds:[$a], validateOnly:true, projectId:"<pid>"}')
  mcporter call chatcut.edit_item --args "$ARGS"
  ```

- 起点三种写法：`fromFrame`（整数帧）/ `from`（"5s" 这类时间字符串）/ `alignTo:"track-end"`（接在轨道末尾，用于**链式拼接**）；
- 时长：`durationInFrames`（整数帧）或 `duration:"3s"`——**不能裸数字**；
- 源内裁剪：`sourceStartFromInSeconds`（源里第几秒开始播）——**没有** startFrame / sourceOffset 这类字段；
- 淡入淡出**单位是秒**：`audioFadeOut:2` 表示 2 秒（不是 2 帧）；要按帧写用 `audioFadeOutDurationInFrames`；
- 转场：`{"type":"transition","assetId":"builtin:tr-cross-dissolve","outgoingItemId":"<前段>","incomingItemId":"<后段>"}`；内置 id 还有 `builtin:tr-dip-to-black`（渐黑）、`builtin:tr-audio-cross-fade`（音频交叉淡化）；同一接缝重复加同类转场是「替换」不是叠加；
- 给**新加的**元素挂 effect / 转场要两步：先 add 拿到返回的 id，再在第二次调用里 attach（不能引用还不存在的条目）；
- **动语义内容（按说话剪）不要用 edit_item**——那要走 Script（见 4b）；字幕更不要用 edit_item（字幕不是普通时间线条目，用 `edit_captions`）；
- 每次改前先 `validateOnly:true` 干跑，通过再真跑。

#### 4b. 语义剪辑（Script：按说话内容剪）

这是 ChatCut 的招牌能力：「把讲 XX 那段剪出来」「去掉重录的那一遍」「把三句话的版本拼出来」。

机制：`read_script` 把**讲述内容**展开成一份可编辑的 `timeline.md`（每句话一行），你在文件里删 / 移 / 重复行，`apply_script` 把编辑提交为真正的时间线剪辑。

```bash
# 1) 展开讲述稿（call 后拿返回的 timelineMd，或工作区形式的 timeline.md）
mcporter call chatcut.read_script --args '{"projectId":"<pid>"}'

# 2) 在文本里编辑：删一句话 = 删那一行（或只划掉想删的词）
#    移动行 = 改顺序；重复行 = 复制行（新副本去掉 @N 后缀）

# 3) 提交（先 preview 看结果，确认后去掉 preview 再提交）
mcporter call chatcut.apply_script --args '{"preview":true,"timelineMd":"<编辑后的全文>","projectId":"<pid>"}'
```

编辑语法要点（中文场景尤其注意）：

- 删一整行：直接删掉那行，或用 `~~[s5] hello world~~` 整行包裹；
- 只删句中的词：`[s1] 过去~~呢~~一个月`——**不能**跳过中间的词重写整句，**不能**给中文加空格；
- 行首的 `[sN]` 是源段编号，**不许改写句子内容**（是不是原话很重要——这让剪辑不会伪造没说过的话）；
- 同一段出现多次时行会带 `@1`/`@2` 后缀（`[s5@2]`），编辑时**保留后缀**——去掉后缀 = 变成另一次重播；
- 剪「气口」（停顿）：`read_script` 时加 `showSilence:true`，然后 `~~[silence=0.8s]~~` 删掉或 `[silence=0.8s→0.2s]` 压缩；
- 从中间删掉内容会产生**新的剪辑分界**（前后两段各自成条）——这是正常现象，不是出错；跳切明显的话，后续用 B-roll / 画面盖一下；
- 改完先 `preview:true` 看结果，再正式提交；提交后 `timeline.md` 会重新生成（之前的编辑痕迹清空）。

**中文可用性提示**：ChatCut 的编辑语法明确支持中文（文档专门有中文规则），但**中文转写 / 语义剪辑准确度尚无实测**（之前只实测过英文素材）。用中文内容前，先拿一条短视频免费试一次转写质量，再决定是否用它做正式剪辑。

### 第 5 步：字幕（转写 / 样式 / 翻译）

```bash
# 导入后一般已自动转写；没转写就手动触发（需指定 assetId）
mcporter call chatcut.trigger_transcript --args '{"asset":"<aid>","projectId":"<pid>"}'
# 等转写完成
mcporter call chatcut.track_progress --args '{"action":"wait","target":"transcription","assetIds":"<aid>","projectId":"<pid>"}'

# 读字幕（卡片模型：每张卡有 id / 文本 / 时间）
mcporter call chatcut.read_captions --args '{"projectId":"<pid>"}'

# 改字幕：启用 / 样式 / 模板 / 双语 / 翻译 / 改某张卡的文本
mcporter call chatcut.edit_captions --args '{"action":"enable","projectId":"<pid>"}'
mcporter call chatcut.edit_captions --args '{"action":"set_card_text","cardId":"<cardId>","text":"替换文本","revision":"<rev>","projectId":"<pid>"}'
```

要点：

- **改某张卡的文本前必须先 `read_captions`**（拿 cardId 和 revision）；样式 / 开关 / 翻译这类轨道级操作用直接调用；
- 实测准确度：英文素材关键词全部命中正确句子（5/5）；中文未测；
- 字幕是独立图层，**不要**当成时间线条目去移动 / 删除。

### 第 6 步：预览（改一眼看一次）

```bash
# 出时间线帧图核对（默认 9 帧，可指定帧号看细节）
mcporter call chatcut.preview_timeline --args '{"projectId":"<pid>","viewerFrameCount":9}'
```

- 要判断某个切点 / 淡入淡出对不对时，用 `viewerFrames` 指定精确帧号再出图（看相邻帧）；
- 预览帧是「采样时刻」——涉及变化（切点、运动）的判断要看相邻帧，不能只看单帧；
- 人环场景可以用插件的 `show_preview` 在聊天里挂预览小窗，或直接打开 `editorUrl` 看。

### 第 7 步：导出

```bash
# 提交导出（无人值守用 cloud；要带字幕文件用 format:"subtitles" + subtitleFormat:"srt"）
mcporter call chatcut.submit_export --args '{"format":"video","renderMode":"cloud","resolution":"720p","codec":"h264","projectId":"<pid>"}'

# 等待并取结果链接（renderIds 来自上一步返回）
mcporter call chatcut.track_export --args '{"action":"wait","renderIds":"<renderId>","projectId":"<pid>"}'
```

要点：

- `renderMode:"local"` 渲染在本地浏览器里做（快、不耗云端资源）——**但要求编辑器页面开着，失败不会自动回落云端**；无人值守场景直接用 `"cloud"`（实测一次 ~12 秒渲染完一条 17 秒的片子）；
- `resolution` 可选 480p / 720p / 1080p（默认 1080p）；社群分享 720p 足够；
- 导出规格实测：h264 / mp4，可直接下载；
- **实测坑：产物音频比画面长约 0.05 秒**——拿到文件后用 ffmpeg 修剪对齐（`-shortest` 或裁掉尾部），别原样发给用户（微信里可能尾部黑屏）。

### 第 8 步：下载验收

导出结果拿到 `downloadUrl` 后下载到本地，然后照主文档的「成品验收清单」过一遍：

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name -show_entries format=duration -of compact out.mp4
```

重点核对：H.264 + AAC、时长、音频不比画面长。

---

## 三、工具地图（61 个，按用途分组）

用 `mcporter list chatcut` 现取清单；名单纯索引用（2026-10-09 快照）：

- **项目（10）**：list_projects、create_project、read_project、target_project、edit_project、delete_project、duplicate_project、restore_project、get_editor_url、show_preview、web_browser、report_user_friction
- **素材（10）**：import_media、browse_assets、browse_library、inspect_asset、edit_asset、manage_media_pool、search_stock_media、search_fonts、request_asset_download、register_converted_video
- **时间线（10）**：manage_timelines、preview_timeline、edit_item、inspect_item、split_item、edit_track、manage_markers、manage_design_style、manage_template、manage_skill
- **转写 / 字幕（10）**：trigger_transcript、track_progress、find_transcript、manage_transcript、read_script、apply_script、clean_script、read_captions、edit_captions、video_translation
- **音频 / 配音（6）**：submit_voice、manage_voice、manage_custom_voice、isolate_voice、smooth_audio、detach_audio
- **数字人（3）**：manage_avatar、submit_avatar_video、submit_lipsync
- **生成（9）**：submit_video、submit_image、submit_music、submit_sound、submit_shader、create_motion_graphic_from_code、convert_motion_graphic_to_video
- **导出（3）**：submit_export、track_export、export_motion_graphic_prores

（合计 61。别冻结名单——用前 `mcporter list chatcut` 现取。）

---

## 四、坑与边界汇总

1. **`edit_item` 的 adds/updates 是 JSON 字符串数组**——不是对象数组；用 `jq -n --rawfile` 组装最稳；
2. **时长不能裸数字**——`duration:"3s"` 或 `durationInFrames:90`；
3. **源内裁剪是 `sourceStartFromInSeconds`**——没有 startFrame / sourceOffset；
4. **淡入淡出单位是秒**——`audioFadeOut:2` = 2 秒；
5. **转场重复添加是替换**——同一接缝已有同类转场时不会叠加；
6. **给新元素挂 effect / 转场要两步**——先 add，拿 id，再 attach；
7. **动语义内容用 Script 不用 edit_item**——「把讲 XX 那段剪出来」走 `read_script → 编辑 → apply_script`；
8. **字幕不是时间线条目**——读用 read_captions，改用 edit_captions，别用 edit_item 动它；
9. **批量导入 1–16 个/批**，失败用同一 assetId 重试；导入时目标项目要在浏览器开着；
10. **导出 `renderMode:"local"` 失败不自动回落**——无人值守用 `"cloud"`；
11. **导出产物音频比画面长 0.05s**——交付前对齐修剪；
12. **授权 / 长时间后台进程要用 tmux 挂**——pi 会回收后台 bash；**临时服务会话用 `pi-` 前缀命名**（如 `pi-chatcut-import`）：pi 的 session-guard 只允许 agent 关闭 `pi-` 前缀的 tmux 会话，其他名字创建后清不掉（会被拦截），这是 2026-10-09 实测确认过的坑；
13. **`mcporter config add` 别在仓库里跑**——会写脏当前目录；
14. **费用边界**：免费层只含「纯剪辑 + 字幕 + 导出」；MG / 音乐 / 音色克隆 / 数字人 / 视频生成 / 翻译要积分或订阅——**别在免费层悄悄调这些**（调用前想清楚是否真要花钱）；
15. **中文转写 / 语义剪辑准确度未实测**——正式用前先小样试。

---

## 五、更新记录

| 日期 | 更新 |
|---|---|
| 2026-10-04 | Buzz 完成免费层全流程实测（T1–T5）：导入 / 时间线 / 转写 / 导出全不计积分；mcporter 直连打通（60 个工具） |
| 2026-10-09 | Buzz 复核连通性（凭证自动刷新、CC 插件 Connected）；Gatsby 核对 61 个工具与关键参数，本文落成 |

以后接触 ChatCut 有新发现（新坑、工具增减、计费变化），顺手更新本文件并记项目 `CHANGELOG.md`。
