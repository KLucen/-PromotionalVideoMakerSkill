# 通用工具、数据接口与适配边界

## 随 Skill 提供的工具

| 脚本 / 命令 | 输入与用途 | 支持边界 |
| --- | --- | --- |
| `scripts/probe_source.py` | 当前源视频 → SHA、实际帧数、整数 PTS/time base、有理数秒、显式流结束与尾曝光、包端点差异 | 单视频流；所需时序缺失或冲突时停止，不能用平均 fps 补造；不拆语义稿 |
| `scripts/pv_tools.py analyze` | 已确认 CFR 的区间/ROI → 逐帧差异、连贯区域、网格候选、PNG/JSON | `--cfr` 是调用方声明，不是自动检测；候选不是已确认独立稿；输出均匀时间不用于 VFR/量化来源 |
| `scripts/pv_tools.py diff` | 两张已提取位图 → AB、放大 RGB 差、双色轮廓与局部指标 | 不形变对齐、不插帧、不生成角色、不代替看图；尺寸不同时先核实画布关系 |
| `scripts/pv_tools.py validate-timeline` | 文档中的 CFR 时间轴 → 曝光覆盖、边界、资产存在及 strict/adapted 检查 | 只接收声明的 schema；不验证图像内容、相位语义或音频；VFR 需按精确 PTS 表另验 |
| `scripts/verify_encoded.py` | 当前输出 + 来源元数据 → 来源身份/实际 PTS、输出尺寸/PTS/尾曝光、原 AAC 配置/载荷/时戳/priming、完整解码与文件不变 | 单视频+单 AAC、零起点来源、原 AAC 复制及 strict_source；不支持替换音轨/其他音频 codec/任意源起点，也不评价色彩、显示比例或美术 |
| `scripts/test_media_tools.py` | 通用工具的精确时序、音频 tick、包签名和文件保护测试 | 不是某部 PV 的美术测试，不替代输出文件实际验证 |

Python 3.11+、FFmpeg/FFprobe 可运行来源和编码检查；`pv_tools.py` 还需 NumPy/OpenCV/Pillow。使用项目已有兼容环境，不为不同帧数而升级工具。总帧数来自当前文件，没有固定长度或角色配额；具体 codec/时序仍受上表能力限制。

## 调用示例

以下路径仅为占位示例，换成当前项目的实际来源与新报告路径。报告工具拒绝覆盖既有证据。

```powershell
$skillDir = Join-Path $HOME '.codex/skills/pv-character-replacement'
python "$skillDir/scripts/probe_source.py" source.mp4 --output qa/source_meta.json
python "$skillDir/scripts/pv_tools.py" diff refs/source-A.png refs/source-B.png --output qa/source-A-B
python "$skillDir/scripts/verify_encoded.py" output/master.mp4 --metadata qa/source_meta.json --report qa/master-check.json
python "$skillDir/scripts/verify_encoded.py" output/comparison.mp4 --metadata qa/source_meta.json --side-by-side --report qa/comparison-check.json
```

默认全片验证全部源帧；片段用零基 `--start`/`--end`，end 不包含。帧边界从真实曝光/PTS 中取，不能照抄示例或另一工程范围。AAC 截片遵循最近音频 tick、预卷和完整包规则；报告音视频起点量化残差，不能加任意容差掩盖一采样偏移。

真实尾曝光使用有效的 `start_pts + duration_ts - last_pts`，不默认用最后包 duration 或 `1/fps`。包端点与流结束不同时保留诊断，核对容器编辑列表、重排和实际解码；不通过擅改时序消除差异。

对不在支持范围的来源或 `adapted_motion`，先建立适用的来源/批准输出时间表与检查器。不要只关闭失败检查来扩大工具能力，也不要宣称此工具自动处理所有格式。

## 新项目的参数从哪里来

| 参数或决策 | 权威来源 |
| --- | --- |
| 帧数、画布尺寸、time base、PTS、显示/色彩信息、音轨与尾边界 | 当前源文件的实测元数据 |
| 镜头范围、独立绘稿、源循环、表情、人物与可见残片 | 当前源画面的语义分析与已核曝光表 |
| 同稿重复、实例变换与相机运动 | 当前原尺寸参考、局部差值及配准证据 |
| 角色比例、画风、参考职责与采用版本 | 当前角色基准、试制结果和权威素材清单 |
| 删除/保留 mask、字幕供体、色键和 ROI | 当前镜头所有适用曝光中的层级与可观察像素 |
| 批次、缓存、并行度与检查点 | 实测资源成本、依赖关系、用户授权及运行状态 |
| 输出帧/音轨、局部重编码范围与拼接方式 | 制作约定、实际编码依赖与独立验证结果 |

这些参数作为当前工程数据或显式函数参数传入。不要在通用脚本里嵌入某支 PV 的帧号、固定周期、图片名单、人物颜色、尺寸或每秒帧数。新项目先完成来源和代表风险试制，再扩大处理范围；旧代码存在不代表其假设已适配。

## 项目工具可以怎样分工

需要时在项目内实现：源分析与实例跟踪、任务/素材登记、曝光解析、图层合成、编码、技术检查、静态/动态审阅、交付汇总。工具名称不限，职责和输入输出需登记在项目索引。

分析器输出候选及置信证据；选择表决定采用稿；合成器读取显式曝光而不是猜最近姿势；编码器读取精确时序；交付汇总引用实际已完成的独立验证报告。各阶段不得自动把自己的成功升级成下阶段验收。

局部返修的语义覆盖、几何配准、编码区间与不变证据见 [局部换人与增量返修](targeted-revisions.md)。受限条件下的压缩包替换只是可选优化，不能把对某一编码配置可用的项目脚本当通用拼接器。
