# 短剧投流素材批量剪辑流水线（WorkBuddy Skill）

短剧海外投流素材批量剪辑：原片拼接 + 二创解说双轨，一键跑完「勘察 → 剧情地图 → 选段规划(全局去重) → 界面元素 → TTS 配音 → ffmpeg 批量构建 → 质检自纠」全流程，只交付最终合格版。

## 能力

- **素材勘察**：目录盘点、ffprobe 规格、抽帧验字幕/贴片/画面类型、SRT → cue 表 → 剧情地图
- **选段规划**：镜头切点检测 + 边界吸附跳剪、五类模板（多集串联/单个高潮/高光混剪/高光前置/二创解说）、**全局唯一审计（0 重叠才准渲染）**
- **解说制作**：edge-tts 神经语音多语种配音、逐句对位排程、密度控制（停顿 ≤2s、无 ≥2.5s 无声段）、ASS 字幕烧录
- **一键构建**：720×1280 / H.264 / CRF19 / AAC 160k，logo + 片头剧名条 + 静态落版三件套，码率自纠（不足自动降 CRF 重建）
- **六维质检**：规格 / 电平 / 静音 / 转录 / 画面 / 命名

## 目录结构

```
SKILL.md               # skill 主入口：交付契约 + 七阶段流程 + 差异适配
references/spec.md     # 硬性规范速查（九段式命名/输出规格/界面元素）
references/sop.md      # 完整 SOP（核心原则/选段规划/构建/质检/踩坑 15 条）
scripts/
  survey.py            # Stage 1: 素材勘察
  srt_to_cues.py       # Stage 1: SRT -> cue 表
  scene_cuts.py        # Stage 3: 镜头切点检测
  audit_segments.py    # Stage 3: 全局选段唯一性审计
  gen_assets.py        # Stage 4: logo/剧名条/落版三件套（PIL）
  gen_tts_edge.py      # Stage 4: edge-tts 配音 + durations.json
  build_clip.py        # Stage 5: 单条素材构建（ffmpeg 滤镜链）
  pipeline.py          # Stage 5: 审计 -> 构建 -> 自纠 -> QC 一键编排
  qc_clips.py          # Stage 6: 五维质检
  common.py            # 公共工具（ffmpeg 解析/probe/吸附）
```

## 依赖

```bash
pip install imageio-ffmpeg pillow edge-tts   # Python 3.10+
```

ffmpeg 由 imageio-ffmpeg 自带，也可用 `FFMPEG_PATH` 环境变量指定。

## 硬性默认指标

1. **单条时长约 2 分钟**（正片+落版 ≈117–125s），规划前先验算素材总量；
2. **解说密度必须够**：句间停顿 ≤2s，交付前 silencedetect 验证零 ≥2.5s 无声段，BGM 全程覆盖。

## 来源

由 2026-11 海外短剧投流实战项目（TK《假离婚真后悔》、SODA《Pregnant by My Husband's Friend》等）复盘提炼，全部步骤与参数经过实测验证。
