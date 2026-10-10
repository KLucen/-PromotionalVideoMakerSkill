# Promotional Video Maker Skill

面向不同长度、帧数和帧率的高质量角色替换 PV 制作 Skill：从当前来源的独立绘稿、真实曝光、人物实例与图层变化出发，保留原画风、分镜、关键姿势和演出节奏。

Skill 名称：`pv-character-replacement`。它是制作工作流与检查工具，不是单命令视频生成器，也不用于普通换脸。

## 内容

- [Skill 入口](pv-character-replacement/SKILL.md)：制作约定、核心流程与参考资料导航。
- [制作流程](pv-character-replacement/references/production-playbook.md)：不同规模与时序的处理、阶段门槛、任务记录、提速与终版条件。
- [局部返修](pv-character-replacement/references/targeted-revisions.md)：语义覆盖、双人表情变体、几何配准、编码范围与不变证据。
- [故障定位](pv-character-replacement/references/failure-patterns.md)：可观察症状、处理依据与必须复查的范围。
- [脚本地图](pv-character-replacement/references/script-map.md)：工具职责、输入输出、命令和适用范围。
- `references/`：拆稿、提示词、图层、连续性和交付检查。
- `scripts/`：二维差值、曝光表校验、精确来源时序、编码/AAC 校验及单元测试。

## 如何适配不同 PV

总帧数影响解码、合成和编码资源，不直接决定生图张数。独立绘稿、曝光、实例、字幕/特效相位与风险共同决定制作量。

| 来源特点 | 处理方式 |
| --- | --- |
| 长持帧、重复循环多 | 核定绘稿复用，保留每次曝光与独立背景/文字变化 |
| 短片但动作/表情密集 | 按真实局部变化拆稿，不套固定张数配额 |
| 运镜多或多人重叠 | 分离相机、人物实例和遮挡关系 |
| 帧率不同或时间间隔不均匀 | 使用实测 PTS，重新建立当前来源曝光表 |
| 长片且独立稿多 | 流式处理、依赖批次、缓存与恢复点；保持同样的质量门槛 |

帧数、画布、镜头边界、循环长度、色键和 ROI 均由当前项目提供，不依赖某一支 PV 的脚本或帧号。

## 默认制作规则

- [未修改区域优先保留](pv-character-replacement/references/layers-and-continuity.md#未修改区域优先保留)：字幕区经整段曝光检查与新旧人物及编辑支持不交叠时，沿用对应原帧区域，只重绘/合成角色所需部分；不冻结字幕和特效。
- [项目状态及时落盘](pv-character-replacement/references/production-playbook.md#项目状态与中断恢复)：记录文件职责、素材版本、当前采用及检查范围；中断或上下文压缩后先恢复磁盘状态，再继续生成，避免重复生图与旧稿回退。

## 安装与调用

在支持 Skill Installer 的 Codex 中发送：

```text
使用 $skill-installer 安装 https://github.com/KLucen/-PromotionalVideoMakerSkill/tree/main/pv-character-replacement
```

也可将完整的 `pv-character-replacement` 目录放入 `$CODEX_HOME/skills`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills`。已有同名 Skill 时先保留原版，再按需要更新。新安装会在下一轮可用。

调用示例：

```text
使用 $pv-character-replacement 制作角色替换 PV，保留原分镜和真实曝光；逐稿检查关键姿势、遮挡、字幕与原速连续性，完成技术和美术两类验收。
```

## 运行要求

- Python 3.11+、FFmpeg/FFprobe：来源时序与编码检查。
- NumPy、OpenCV、Pillow：`pv_tools.py` 的分析和差值功能。
- 可用的图像生成/编辑工具：实际角色绘制；本仓库不提供生图模型或凭据。

运行单元测试：

```sh
python pv-character-replacement/scripts/test_media_tools.py
```

先读取脚本地图中的能力边界。`analyze --cfr` 只是调用方声明恒帧率，不证明源时序；AAC 校验器仅支持其明确范围。技术通过不等于美术通过，稀疏抽帧不替代全片原速审阅。

本仓库只包含 Skill 文档与通用工具，不包含原 PV、音频、角色参考、生成媒体、本地缓存或账户凭据。具体制作案例和专用参数留在各自工程，Skill 保持独立可用。
