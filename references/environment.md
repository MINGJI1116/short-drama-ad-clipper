# 运行环境清单（environment.md）

> 用途：新机器 / 新会话开工前，把本文件内容直接交给执行 AI，避免环境冷启动浪费时间。
> 本项目 2026-11-15 实测：环境摸索耗掉约 40 分钟，全部可由本文件避免。

## 机器与 Shell
- OS：Windows 11（win32），默认 Shell 为 **Git Bash**（POSIX sh）；PowerShell 5.1 可用但非必需
- 用户目录：`C:/Users/LENOVO`；工作缓存区：`D:/workboddy cache/<会话>/`
- 路径含中文与空格：bash 命令一律加双引号；涉及 Windows 原生命令（如 `mklink`）用 `cygpath -w` 转换

## Python（⚠️ 有两个，选错=反复安装失败）
| Python | 路径 | 用途 |
|---|---|---|
| 工作台沙箱 python | PATH 里的 `python` | **pip 无网络**（下载即被杀，SIGTERM），不要尝试 pip install |
| **系统 Python（用这个）** | `C:/Users/LENOVO/AppData/Local/Programs/Python/Python313/python.exe` | 已装齐全部依赖 |

系统 Python 已装依赖：`edge-tts`（解说配音）、`Pillow`（贴片/落版生成）、`imageio-ffmpeg`。
开工前一条命令自检：
```bash
"C:/Users/LENOVO/AppData/Local/Programs/Python/Python313/python.exe" -c "import edge_tts, PIL, imageio_ffmpeg; print('deps ok')"
```

## ffmpeg（⚠️ 无 ffprobe）
- 唯一可用 ffmpeg：`D:/BilibiliConvertQT_v1.0.11/ffmpeg.exe`
- 本 skill 全部脚本通过环境变量取用：**`export FFMPEG_PATH="D:/BilibiliConvertQT_v1.0.11/ffmpeg.exe"`**（每条 Bash 命令都要带，shell 状态不跨调用保留）
- **系统没有 ffprobe**：任何自写脚本/命令禁止依赖 ffprobe，用 `ffmpeg -i` 输出 + grep 解析（Duration/bitrate/流信息）
- ffmpeg 为 9.x：**无 `-filter_complex_script` 参数**（skill 脚本已规避，勿手动加回）

## 网络
- edge-tts 可联网，但**偶发瞬时 503**：单句 probe 成功后整批重跑即可，不要改代码
- GitHub 走 MCP 连接器（owner：`MINGJI1116`，skill 仓库：`MINGJI1116/short-drama-ad-clipper`）
- 工作台沙箱内 pip 无网络（见上），WebSearch/WebFetch 正常

## 字体（贴片/落版用）
- 字体目录：`C:/Windows/Fonts`
- `segoeuib.ttf`（Segoe UI Bold）：**拉丁字符 OK，缺 CJK，中文会渲染成方框**
- 中文剧名贴片需改用 `msyh.ttc`（微软雅黑）系列——生成后必须 ViewImage 验字

## Skill 与代码
- Skill 位置：`C:/Users/LENOVO/.workbuddy/skills/short-drama-ad-clipper/`（本地目录**不是 git 仓库**）
- GitHub 镜像仓库：`MINGJI1116/short-drama-ad-clipper`（main 分支），更新用 github MCP 的 push_files（本地无 git 凭据，不要尝试本地 git push）
- Skill 脚本读取的环境变量：`FFMPEG_PATH`（ffmpeg 路径）、`VBR_TARGET`（设置后 build_clip.py 走 ABR 模式，值如 `2800`，用于暗场剧码率保底）

## 素材目录约定（用户既有习惯）
```
D:\工作专用\<剧名>\
├── 成片\                 # 带烧录字幕的成片（第NN集.mp4，可能有"卡点集/付费集"等后缀）
├── 无字幕文件\           # 干净画面（用于解说条）
├── 字幕文件\             # SRT（第NN集.srt）
├── 音轨\BGM|人声|音效\    # 分集音轨（第NN集.wav）
├── 海报\  翻译后的剧本文档\
└── 成片素材输出\          # 交付目录（成片 + 交付清单.md）
```
- **开工前先核对每集文件名能否用单一 pattern 匹配**（如 `第%02d集.mp4`）；有特殊后缀或两目录写法不一致时，先用硬链接建规范化目录再进流水线（见 `references/pitfalls.md` 案例 1）
- logo 文件常在 `D:/工作专用/` 根下（如 `Soda-TV圆角.png`）

## 快速启动命令模板
```bash
export FFMPEG_PATH="D:/BilibiliConvertQT_v1.0.11/ffmpeg.exe"
export VBR_TARGET=2800   # 暗场剧建议默认开启
PY="C:/Users/LENOVO/AppData/Local/Programs/Python/Python313/python.exe"
cd "C:/Users/LENOVO/.workbuddy/skills/short-drama-ad-clipper"
"$PY" scripts/survey.py "<素材根目录>" --out "<work>/survey.json" --frames "<work>/frames"
```
