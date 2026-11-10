#!/usr/bin/env bash
# record-vertical.sh —— 用本机摄像头录竖屏短视频
#
# 为什么需要它：短视频平台（抖音 / 小红书 / 视频号）要 9:16 竖屏，而笔记本内置摄像头
# 是 16:9 横屏传感器、往往最高只到 720p。所以做法是「录横屏母版 → 从中央裁出 9:16 条带
# → 放大到 1080×1920」。裁切只保留画面正中最有价值的部分，母版单独留存，日后要改画幅
# 或做横屏版还能重裁（一鱼多吃的素材源头）。
#
# 用法：
#   ./scripts/record-vertical.sh                  # 开录，按 Ctrl+C 结束
#   ./scripts/record-vertical.sh -d 30            # 录 30 秒自动停
#   ./scripts/record-vertical.sh -r 4:5 -d 15     # 4:5 画幅（小红书图文 / 视频）
#   ./scripts/record-vertical.sh --check          # 校准构图：录 2 秒，出带取景框的截图
#   ./scripts/record-vertical.sh --list           # 列出摄像头与麦克风编号
#   ./scripts/record-vertical.sh --no-audio -d 10 # 只录画面
#   ./scripts/record-vertical.sh --raw -d 10      # 只留横屏母版，不转竖屏
#
# 构图提示：人站在画面正中，脸放在画面中间偏上的位置；横屏母版里只有中间那条
# 竖条会被保留，靠边的部分会裁掉。第一次用先跑一次 --check 看取景框。

set -euo pipefail

# ---------- 默认参数 ----------
CAMERA=0                              # 摄像头编号（--list 查）
MIC=1                                 # 麦克风编号（--list 查）
SOURCE_SIZE=1280x720                  # 采集分辨率：内置摄像头常见上限，其它设备可改
FPS=30
DURATION=0                            # 0 = 手动 Ctrl+C 结束
RATIO="9:16"                          # 成片宽高比
HEIGHT=1920                           # 成片高度，宽度按比例算
CRF=20                                # 画质（18-23 之间，越小越清晰、文件越大）
OUTDIR=""
AUDIO=1
RAW_ONLY=0
MODE="record"                         # record | check | list

usage() {
  # 打印文件开头的连续注释行（跳过 shebang、遇到第一条非注释就停）
  awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--duration)    DURATION="$2"; shift 2 ;;
    -o|--outdir)      OUTDIR="$2"; shift 2 ;;
    -r|--ratio)       RATIO="$2"; shift 2 ;;
    -s|--source-size) SOURCE_SIZE="$2"; shift 2 ;;
    -c|--camera)      CAMERA="$2"; shift 2 ;;
    -m|--mic)         MIC="$2"; shift 2 ;;
    --fps)            FPS="$2"; shift 2 ;;
    --height)         HEIGHT="$2"; shift 2 ;;
    --crf)            CRF="$2"; shift 2 ;;
    --no-audio)       AUDIO=0; shift ;;
    --raw)            RAW_ONLY=1; shift ;;
    --check)          MODE="check"; shift ;;
    --list)           MODE="list"; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "未知参数：$1（用 -h 看用法）" >&2; exit 1 ;;
  esac
done

# ---------- 依赖检查 ----------
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "找不到 ffmpeg，先装：brew install ffmpeg" >&2
  exit 1
fi

# ffmpeg 因动态库断链起不来时（报 Library not loaded），错误信息里会点名缺哪个库。
# 修法是重装它依赖的上游包（例如 brew reinstall zeromq），不是给本脚本塞环境变量。
check_ffmpeg_runs() {
  local err
  if ! err=$(ffmpeg -version 2>&1 >/dev/null); then
    if grep -q "Library not loaded" <<<"$err"; then
      echo "ffmpeg 跑不起来：动态库断链。" >&2
      grep -m1 "Library not loaded" <<<"$err" | sed 's/^/  /' >&2
      echo "修复：重装提供该库的上游包，例如 brew reinstall zeromq（再 brew reinstall ffmpeg）。" >&2
    else
      echo "$err" >&2
    fi
    exit 1
  fi
}
check_ffmpeg_runs

# ---------- 列出设备 ----------
if [[ "$MODE" == "list" ]]; then
  # 这个调用一定返回非 0（它只是想列出设备），所以吞掉退出码
  ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | grep -E "AVFoundation|\[[0-9]+\]" || true
  exit 0
fi

# ---------- 路径 ----------
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
OUTDIR="${OUTDIR:-$ROOT/tmp/recordings}"
mkdir -p "$OUTDIR"

# ---------- 裁切与输出尺寸 ----------
# 目标画幅 rw:rh，比如 9:16
RW=${RATIO%%:*}
RH=${RATIO##*:}
SRC_W=${SOURCE_SIZE%x*}
SRC_H=${SOURCE_SIZE#*x}

# 母版里能裁出的最大条带：先按高度算宽度，宽度超了再反过来按宽度算高度
CROP_W=$(( SRC_H * RW / RH ))
CROP_H=$SRC_H
if (( CROP_W > SRC_W )); then
  CROP_W=$SRC_W
  CROP_H=$(( SRC_W * RH / RW ))
fi
# H.264 要求偶数尺寸
CROP_W=$(( CROP_W / 2 * 2 ))
CROP_H=$(( CROP_H / 2 * 2 ))
CROP_X=$(( (SRC_W - CROP_W) / 2 ))
CROP_Y=$(( (SRC_H - CROP_H) / 2 ))

OUT_H=$HEIGHT
OUT_W=$(( OUT_H * RW / RH / 2 * 2 ))
SCALE_CHAIN="crop=${CROP_W}:${CROP_H}:${CROP_X}:${CROP_Y},scale=${OUT_W}:${OUT_H}:flags=lanczos"

# 采集命令组装成全局数组后直接后台起 ffmpeg：这样 $! 拿到的是 ffmpeg 自己的 PID。
# 若包一层函数再 &，拿到的是子 shell 的 PID，信号转不到 ffmpeg，录制停不下来。
REC_CMD=()
assemble_record_cmd() {
  local input="$1"
  local output="$2"
  shift 2
  REC_CMD=(ffmpeg -hide_banner -loglevel warning -stats
           -f avfoundation -framerate "$FPS" -video_size "$SOURCE_SIZE" -i "$input")
  if [[ "$DURATION" != "0" ]]; then
    REC_CMD+=(-t "$DURATION")
  fi
  REC_CMD+=(-c:v libx264 -preset veryfast -crf "$CRF" -pix_fmt yuv420p)
  REC_CMD+=("$@")
  REC_CMD+=(-movflags +faststart "$output")
}

# ---------- 构图校准 ----------
if [[ "$MODE" == "check" ]]; then
  RAW_TMP="$OUTDIR/.framing-check-raw.mp4"
  PNG="$OUTDIR/$(date +%Y%m%d-%H%M%S)-framing.png"
  echo "▶ 录 2 秒用于校准构图…"
  DURATION=2
  assemble_record_cmd "$CAMERA:none" "$RAW_TMP"
  "${REC_CMD[@]}"
  # 在母版上把「会保留的那条竖带」画成红框，剩下的部分会被裁掉
  ffmpeg -hide_banner -loglevel error -ss 1 -i "$RAW_TMP" \
    -vf "drawbox=x=${CROP_X}:y=${CROP_Y}:w=${CROP_W}:h=${CROP_H}:color=red@0.9:t=6" \
    -frames:v 1 -y "$PNG"
  rm -f "$RAW_TMP"
  echo
  echo "取景框截图：$PNG"
  echo "红框以内 = 成片里能看到的画面（${CROP_W}×${CROP_H}），框外会被裁掉。"
  echo "请把脸摆进红框、并放在框的上半部（成片顶部常留给标题）。"
  echo "满意后再运行 $0 正式录制。"
  exit 0
fi

# ---------- 正式录制 ----------
TS=$(date +%Y%m%d-%H%M%S)
RAW_FILE="$OUTDIR/${TS}-raw.mp4"
VERT_FILE="$OUTDIR/${TS}-vertical.mp4"

if [[ "$AUDIO" -eq 1 ]]; then
  INPUT="$CAMERA:$MIC"
  AUDIO_ARGS=(-c:a aac -b:a 128k -ar 48000)
else
  INPUT="$CAMERA:none"
  AUDIO_ARGS=()
fi

echo "▶ 录制中：摄像头 ${CAMERA}，采集 ${SOURCE_SIZE}@${FPS}fps，音频 $([[ $AUDIO -eq 1 ]] && echo "麦克风 ${MIC}" || echo "关")"
[[ "$DURATION" == "0" ]] && echo "  按 Ctrl+C 结束录制"

assemble_record_cmd "$INPUT" "$RAW_FILE" ${AUDIO_ARGS[@]+"${AUDIO_ARGS[@]}"}

if [[ "$DURATION" == "0" ]]; then
  "${REC_CMD[@]}" &
  FF_PID=$!
  # Ctrl+C / kill 时把信号转给 ffmpeg，让它把文件头尾写完整（直接杀进程会留下坏文件）。
  # 用 TERM 而不是 INT：非交互 shell 里后台进程组的 SIGINT 会被忽略，转发 INT 会卡死。
  trap 'kill -TERM "$FF_PID" 2>/dev/null || true' INT TERM HUP
  wait $FF_PID || true
  trap - INT TERM
else
  "${REC_CMD[@]}" || true
fi

if [[ ! -s "$RAW_FILE" ]]; then
  echo "录制失败：没有生成文件（检查摄像头是否被其它程序占用、编号是否正确，用 --list 查看）。" >&2
  exit 1
fi

RAW_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$RAW_FILE" 2>/dev/null || echo 0)
echo "✔ 母版：${RAW_FILE}（${RAW_DUR}s）"

if [[ "$RAW_ONLY" -eq 1 ]]; then
  exit 0
fi

# 转竖屏：裁中央条带再放大，音频直接转码（不用 -c:a copy，避免时间戳对不齐）
echo "▶ 转竖屏 ${OUT_W}×${OUT_H} …"
if [[ "$AUDIO" -eq 1 ]]; then
  ffmpeg -hide_banner -loglevel error -i "$RAW_FILE" \
    -vf "$SCALE_CHAIN" \
    -c:v libx264 -preset veryfast -crf "$CRF" -pix_fmt yuv420p \
    -c:a aac -b:a 128k -movflags +faststart "$VERT_FILE"
else
  ffmpeg -hide_banner -loglevel error -i "$RAW_FILE" \
    -vf "$SCALE_CHAIN" \
    -c:v libx264 -preset veryfast -crf "$CRF" -pix_fmt yuv420p \
    -an -movflags +faststart "$VERT_FILE"
fi

echo "✔ 竖屏成品：$VERT_FILE"
echo
echo "母版留在 ${OUTDIR}，日后要改画幅或做横屏版可以从它重裁。"
echo "上传前记得过一遍发布前检查清单（无导流 / AI 标注 / 平台适配）。"