# Promotional Video Maker Skill

面向高质量角色替换 PV 的 Codex Skill：保留原片画风、分镜、关键姿势和演出节奏，系统处理逐稿生成、遮挡、字幕、连续性与成片验收。

Skill 名称：`pv-character-replacement`。它是制作工作流与检查工具，不是单命令视频生成器，也不用于普通换脸。

## 内容

- [Skill 入口](pv-character-replacement/SKILL.md)：制作约定、核心流程与参考资料导航。
- [制作流程](pv-character-replacement/references/production-playbook.md)：阶段门槛、任务记录、提速与终版条件。
- [故障经验](pv-character-replacement/references/failure-patterns.md)：真实失败、已验证修复、无效尝试与待解决问题。
- [脚本地图](pv-character-replacement/references/script-map.md)：工具职责、输入输出、命令和适用范围。
- `references/`：拆稿、提示词、图层、连续性和交付检查。
- `scripts/`：二维差值、曝光表校验、精确来源时序、编码/AAC 校验及单元测试。

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

本仓库只包含 Skill 文档与通用工具，不包含原 PV、音频、角色参考、生成媒体、本地缓存或账户凭据。可莉工程链接仅用于追溯案例，工程专用脚本不能直接视为通用工具。
