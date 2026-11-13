# short-drama-ad-clipper

短剧海外投流素材**一次性剪辑** Skill（WorkBuddy Agent Skill）。

给一套短剧素材（成片 / 无字幕成片 / 字幕 / BGM / logo），一键跑完：勘察 → 一次问齐 → 选段规划 → 元素与配音 → 批量构建 → 五维质检 → 九段式命名交付。中间审计失败、码率不足、静音超标等问题全部内部自检自纠，只交付最终合格版。

## 核心规则（全部经实战复盘沉淀）

1. **交付契约**：全程只与用户交互两次——开工前一次问齐（剧代号必问），交付时一次；其余内部静默完成；
2. **单条约 2 分钟**：每条素材（正片 + 落版）目标 ≈117–125s；
3. **默认只做跳剪拼接**：按剧情线跳剪、切点吸附镜头边界，不默认产出混剪/高光前置/解说多类型；
4. **每集必用**：`all_episodes` 渲染前强校验，缺集 exit 3 拦截，不存在"某集忘了用"；
5. **开场直接进事件，剧名唯一位置**：无片头大标题；剧名贴片底部居中、0s 起常驻至正片结束，落版同位置衔接。

## 目录结构

```
SKILL.md               # 总控：交付契约、硬指标、7 Stage 编排、素材差异适配
references/
  spec.md              # 硬性规范速查：九段式命名、输出规格、界面元素、解说规范
  sop.md               # 完整 SOP：9 原则、构建管线、六维质检、22 条踩坑记录
scripts/
  common.py            # 公共工具（ffmpeg 路径、运行命令、时长解析）
  survey.py            # Stage 1 素材勘察（ffprobe + 抽帧）
  srt_to_cues.py       # SRT → cue 表 → 剧情地图
  scene_cuts.py        # 镜头边界检测（scene 0.30 / AI 剧 0.15）
  audit_segments.py    # 全局去重 + 每集覆盖审计（渲染前拦截）
  gen_assets.py        # PIL 生成 logo 贴片 / 底部剧名贴片 / 落版
  gen_tts_edge.py      # edge-tts 神经语音逐句配音 + durations
  build_clip.py        # project.json 驱动单条构建（滤镜图 / 音频链）
  qc_clips.py          # 规格码率电平质检
  pipeline.py          # 一键流水线：审计→构建→质检→失败自动重试→唯一汇总
```

## 快速开始

```bash
pip install imageio-ffmpeg pillow edge-tts

python scripts/survey.py <素材目录> --out survey.json --frames frames
python scripts/scene_cuts.py <成片目录> shots --max 18 --threshold 0.30
python scripts/pipeline.py project.json --min-vbr 2500 --retries 2 --frames qc_frames
```

`pipeline.py` exit 0 = 全部 PASS，可直接交付。project.json 的 schema 见 `scripts/build_clip.py` 文档字符串。

## 输出规格

720×1280 / H.264 / 30fps / 码率 ≥2500kbps（不足自动降 CRF 重试）/ AAC 160k，九段式命名 `时间_序号_中文剧名_剧代号_集数_素材分类_时长_缩写_自定义项`。

## 来源

由《假离婚真后悔》(OAEN2457) 与《Pregnant by My Husband's Friend》两个实战项目复盘提炼，全部规则经用户逐条确认。
