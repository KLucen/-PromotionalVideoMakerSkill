# 脚本地图：职责、输入、输出与边界

## 随 Skill 的通用工具

| 脚本 / 命令 | 用途 | 不负责什么 |
| --- | --- | --- |
| `scripts/probe_source.py` | 从FFprobe记录源SHA、整数PTS/time base、精确有理数秒、显式流结束边界/尾曝光与包端点差异；不覆盖旧报告 | 不拆语义稿、不决定人物重复、不使用平均fps推时间；流时序缺失/冲突需适用的专门分析 |
| `scripts/pv_tools.py analyze` | 对明确CFR区间逐帧做ROI差异、连贯区域和网格候选分析，导出候选PNG与JSON | `--cfr`是调用方声明，不是自动检测；输出的均匀帧时间不是VFR/量化时序依据 |
| `scripts/pv_tools.py diff` | 对两张已提取位图输出AB、RGB差值放大、双色轮廓和局部指标 | 不形变对齐、不插帧、不生成角色、不代替实际看图 |
| `scripts/pv_tools.py validate-timeline` | 检查其文档格式的曝光无缺口/越界、资产存在、strict/adapted边界 | 不接收可莉工程特殊schema；不验图像内容/声音/美术 |
| `scripts/verify_encoded.py` | 独立核对来源元数据与实际PTS、输出PTS/尺寸/尾曝光、原AAC包载荷/配置/时间戳/priming、完整解码、文件不变 | 仅单视频+单AAC、零起点源、原AAC复制及strict_source路线；不评价字幕/流畅度/色彩与显示宽高比，不支持改音频/其他音频codec/任意原起点；adapted_motion需按批准的输出时间表另验 |
| `scripts/test_media_tools.py` | 测试精确量化PTS、元数据不一致、音频tick/包签名与文件保护等关键不变量 | 不是全片美术测试，也不替代真实成片核验 |

Python 3.11+标准库及FFmpeg/FFprobe足够运行来源和编码检查；`pv_tools.py`还需NumPy/OpenCV/Pillow。优先使用项目已有环境，不为使用本Skill盲目升级依赖。

PowerShell示例，路径和源/输出换成当前项目；先确认输出报告不存在：

```powershell
$skill = Join-Path $HOME '.codex/skills/pv-character-replacement'
python "$skill/scripts/probe_source.py" source.mp4 --output qa/source_meta.json
python "$skill/scripts/pv_tools.py" diff refs/source-A.png refs/source-B.png --output qa/source-A-B
python "$skill/scripts/verify_encoded.py" output/master.mp4 --metadata qa/source_meta.json --report qa/master-check.json
python "$skill/scripts/verify_encoded.py" output/comparison.mp4 --metadata qa/source_meta.json --side-by-side --report qa/comparison-check.json
```

全片默认检查全部源帧；片段使用0基 `--start`/`--end`，end不包含。复制AAC的截片必须符合脚本的最近音频tick、预卷及完整包规则，不能通过任意容差让一采样偏移合格。源码位图/重编码音轨等其他路线需要适用的检查器，而不是关闭失败字段。

源末曝光取明确的 `start_pts + duration_ts - last_pts`，不默认用最后包的duration或 `1/fps`。本片有B帧重排，包 `max(PTS+duration)` 比显式流结束早10个视频tick；随包工具同时记录差异，不能把这一差异自动“纠正”成改变源时序。其他来源出现此提示，先查容器编辑列表、重排与实际解码，不把本片解释当普遍豁免。

## 可莉工程脚本：不是通用插件

下面的源码在 [已封存工程快照](https://github.com/KLucen/6.1sol-KleePV/tree/c37719a129586a7e14303f94e5858999d2f7b5f2) 的 `production/`，路径相对于该工程根目录。部分脚本嵌有本片镜头范围、1920x1080、24fps、1/16000 time base、文件名或颜色假设。先检查代码和当前输入，不能把它们复制到新PV后当作已适配。下面列核心职责和私人QA脚本家族；不列每个一次性裁切/探针为通用能力。

### 来源、拆稿与任务

| 脚本 | 输入 → 输出 / 作用 | 限制 |
| --- | --- | --- |
| `analyze_source.py` | 原MP4 → `source_meta.json`、候选`source_map`、metrics、全尺寸refs和接触页；顺序解码每帧 | 颜色foreground和阈值是本片方案；元数据秒原版为浮点，不能拿来分析任意新来源的精确分数 |
| `group_source.py` | 候选 → 校准压缩噪声、局部结构差异与源平移，分配cel/曝光 | 只减少有证据的codec副本；族标签不证明姿势 |
| `refine_camera.py` | 原稿/映射 → 全分辨率刚性变换证明与源camera记录 | 不制造人物形变；不能抹掉真实眼手变化 |
| `rigid_source.py` | 两个真实源帧 → 等比相似变换与RGB残差证据 | 证明原作已有运动，不授权把新稿任意扭曲 |
| `delta_reference.py` | 原A/B位图 → prompt用AB/RGB差/双色轮廓/指标 | 只生成分析参考，不生图或插帧 |
| `report_source.py` | 来源映射 → 曝光覆盖、范围及分析局限报告 | 数字覆盖不是语义/美术确认 |
| `audit_late_source.py`、`audit_title_source_copies.py` | 后段/标题关键源稿 → 避免将标题变化算人物动作、核验特定来源重复对 | 只对指定对/当前原尺寸证据成立 |
| `make_generation_jobs.py` | 源map+已有锚点 → 原cel对应的生图任务/缺口 | 已有锚点或库存文件存在不表示已验收 |
| `prepare_oct7_bulk_queue.py` | 当前缺口 → 固定归属队列 | 一次性全片草稿约定的例子，不是默认质量模式 |
| `early_full_worker.py`、`middle_worker.py`、`late_worker_queue.py`、`root_title_worker.py` | 各镜头范围 → 当前原图、局部参考、prompt/job准备 | 仅准备/归档，不因为脚本名worker就自动完成生图 |
| `qa/oct7-root-bulk.py`、`qa/oct7-root-late.py`等私有helper | 指定归属稿 → 参考/完整prompt/job、工具原输出副本、静态评语和封存 | `--no-prior`移除冲突邻稿；不得重写历史seal或伪造工具调用 |

### 选择、时间轴与合成

| 脚本 | 作用 | 重要边界 |
| --- | --- | --- |
| `audit_full_pv_coverage.py` | 汇总实际选择、来源别名、有效映射/缺稿、全帧覆盖、问题和验收状态 | PNG库存、保守cel上限、帧覆盖、已验收分列；不自动选图 |
| `integrate_draft_proposals.py` | 按明确源帧机械采纳私有proposal到共享选稿 | 不授予美术接受；采纳前后核对归属/旧选择 |
| `qa/oct7-full-draft-preflight.py` | 核五批归属、全部195稿的SHA/尺寸/原件、封存和旧323选择不变 | 本批写死数量/路径，迁移时改成当前清单，不机械复用数字 |
| `make_timeline.py` | 当前map、jobs、selection、已核alias → 所有实际曝光及相机矩阵 | 缺cel直接拒绝，不取最近姿势填洞；本片fps/schema专用 |
| `compose.py inspect` | 原帧+当前生成稿 → 实际合成、对照和新旧mask诊断 | 只是诊断，不自动接受；generic路径没有证明覆盖所有文字/转场 |
| `compose.py render` | 已显式映射时间轴 → 顺序逐帧恢复当前源背景/字/FX、叠新人物、写FFmpeg主片 | 原版render固定24/1920/16000与量化公式；`--draft-preview`不等于终版通过 |
| `review_interval.py`、`review_opening_preview.py`、`review_fullpv_root_repairs.py`等 | 时间轴/指定修复 → 原始合成连续曝光、边界页和限定数值探针 | 可能重新合成；不是最终MP4抽帧，也不证明已原速看过 |

### 独立图层模块

| 模块 | 实际职责 |
| --- | --- |
| `opening_layers.py`、`opening_clock_layers.py` | 开场枕头、手/袖前景保护、孤立悬浮钟及几何探针；悬浮钟不套手持钟 |
| `caption_layers.py` | 已核开场字框/笔画恢复，按当前帧防覆盖人物 |
| `dance_caption_layers.py` | 舞蹈歌词独立透明alpha、两阶段供体、禁止错误左字入口带回旧衣 |
| `night_transition_layers.py` | 注册夜色背影/多人matte和旧人离开后的原渐变恢复；保留原星月 |
| `cyan_profile_layers.py`、`cyan_caption_layers.py` | 青空新旧人物各自sky/matte、vacated修复及实际f966换词相位 |
| `star_gestures_layers.py` | 注册星空人物matte、原特效与各歌词相位，排除旧靴/衣色回灌 |
| `star_caption_alternate.py`、`star_extended_captions.py` | 授权真实同句字形的独立数据与对比重建，CN/JP分别注册；非全局粗描边 |
| `star_extended_layers.py`、`middle_transition_layers.py` | 把已核私有合成检查点按实际文件/区间注册；不是泛化到后续镜头的处理器 |
| `raised_caption_layers.py` | 举臂近景独立透明字层与仅实际明亮新主体交叠区的限定对比支持 |
| `title_layers.py`、`prepare_title_layers.py` | 无字/标题/署名相位背景、源可观测供体和镜头限定人物matte/registry |

图层模块的颜色阈值、供体、ROI和文件名必须绑定已验证范围。新增相位/文件需重新核对，不能为修一处扩大全片条件。它们处理观测到的位图层，不代替角色绘制。

### 编码、验收与交付

| 脚本 | 实际职责 |
| --- | --- |
| `verify_preview.py` | 本片单版/对照逐帧PTS、真实尾边界、AAC配置/包载荷/时戳/预卷、全音视频解码与文件不变17项核验 |
| `qa/oct7-compare-master.py` | 使用原视频+已完成主片hstack，不再做3658帧人物合成；核主片PTS和SHA不变，再额外压缩对照 |
| `qa/full-draft-one-pass-2026-10-07/sample_full_video.py` | 从完整MP4顺序解码指定28源/新版样点、7组三帧全图/字区条，记录文件/像素SHA；实际审阅另写报告 |
| `qa/full-draft-one-pass-2026-10-07/run_regressions.py`及`test_*.py` | 81个选定回归覆盖时序/声音、图层限区、字芯、mask、既有版本不变等 | 
| `qa/oct7-delivery-report.py` | 汇总预检、覆盖、封存、回归、两版17项核验、静态审阅与待返修记录，固定SHA | 
| `tools/engineering_archive.py`、`tools/test_engineering_archive.py` | 上传阶段按SHA去重、分卷保存全部文件、字节校验/还原保护和Release远端digest验证 | 

采样脚本只产生诊断，不能自动写美术PASS。字幕检查字段若未覆盖该相位，不能靠其他所有true获得通过。上传脚本不参与画面/流畅度质量，发布须另有用户授权，调用Skill不自动执行它。

## 迁移到另一支 PV

保留数据契约与检查思想，重新建立源元数据、语义mask、真实绘稿/相位表和角色基准。只有来源、尺寸、时序、颜色和遮挡假设都实际核对后才能复用原工程组件。先在当前项目试制，新增受影响回归，再扩展；禁止把固定帧号、f3402字供体、24fps公式或旧文件guard当通用默认。
