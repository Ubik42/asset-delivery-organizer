# M6 交付边界规则验收

## 结论

M6-S1 完成两条基于稳定文件事实的版本化规则，并贯通严格 Profile、中文配置页、问题筛选、演示素材、自动测试和真实运行截图。审计仍严格只读；新规则不会删除、移动或改写任何输入文件。

## 规则证据

| 规则 | 配置 | 问题证据 | 处理边界 |
| --- | --- | --- | --- |
| `path.allowed-roots@1.0.0` | `roots` 可移植相对目录列表 | 受影响文件、观测顶层目录、允许目录、中文建议 | 只报告；移动仍需另行生成并批准整理计划 |
| `file.allowed-extensions@1.0.0` | `extensions`、可选 `ignored_roots` | 受影响文件、观测扩展名、允许格式、中文建议 | 只报告，不自动删除或转换文件 |

错误配置在运行前失败关闭：绝对路径、`..`、重复目录、空格式列表、重复扩展名均有自动测试；中文 Profile 工作区同步标红字段并禁用保存。

## 可复现演示

生成器 `scripts/generate_demo_assets.py` 版本为 1.1.0。仓库现有 5 个不可变合成场景、109 个文件：

- 合规环境交付：16/0；
- 典型供应商问题：12/5；
- 多资产 UDIM 批量：58/0；
- 嵌套多供应商：14/3；
- 交付边界预检：9/4，其中目录问题 2、格式问题 2。

第五个场景还包含 `Documentation/vendor_brief.docx`，用于证明 `ignored_roots` 不会把允许忽略的供应商文档误报为禁用格式。`demo/run-demo.ps1 -Verify` 在每个审计前后校验全部输入字节，所有场景 `write_count=0`。

## 实际界面证据

- `workbench-boundary-profile.png`：五条规则中的目录与格式配置；
- `workbench-boundary-profile-invalid.png`：`../escape` 被字段级阻断；
- `workbench-boundary-path-issues.png`：只筛选目录问题及同步证据；
- `workbench-boundary-format-issues.png`：只筛选格式问题及同步证据；
- `workbench-boundary-success.png`：16 个文件、0 问题成功态；
- `workbench-boundary-narrow.png`：1080×680 窄窗口布局。

全部 PNG 均由 `asset_delivery_organizer.ui_launcher` 通过生产 `MainWindow` 和真实演示 Profile/场景生成，不是设计稿或另画界面。视觉检查确认中文标签、表格、检查器、错误条和禁用按钮没有裁切或低对比问题。

## 生命周期与安装证据

`docs/evidence/gui-lifecycle-m6-s1.json` 记录两次真实 Windows Qt 窗口后端启动：仅测试拥有的 PID 被关闭，启动前存在的 Python 进程全部保留。干净 wheel 审计额外从安装环境运行两条新规则，并复检边界演示输入未变化。

本轮干净安装包为 `asset_delivery_organizer-1.0.0-py3-none-any.whl`（1.1 开发线尚未在 M7 改正式版本号），SHA-256 为 `d345662aad1d0de27bd7bc710d7a023e12cb17074616a89613d2d25a6d55dc35`；`boundary_rules_clean_install` 与 `boundary_audit_input_unchanged` 均通过。

## 明确未做

本阶段没有实现 UDIM 连续性、重复内容、DCC 场景拓扑、材质网络、格式转换或多 DCC Adapter。目录与格式规则只陈述能从文件事实直接证明的结果。
