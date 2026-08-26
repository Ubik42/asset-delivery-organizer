# 0.2.0 交互式工作台发布审计

日期：2026-08-25

范围：M3-S1 中文只读交互闭环

## 结论

Asset Delivery Organizer 已从 CLI-only 内核修正为可安装的中文桌面工作台。现有扫描、规则和报告核心保持宿主无关；用户无需编写命令即可完成目录与规则选择、文件预览、问题证据审查和报告导出。输入目录继续保持严格只读。

## 直接证据

| 验收项 | 实现与证据 | 结果 |
| --- | --- | --- |
| 图形入口 | `ado-ui`，PySide6 可选依赖 | 通过 |
| 用户选择 | 交付目录、Profile、三条启用规则 | 通过 |
| 文件工作区 | 搜索、类型/状态筛选、元数据、图片/文本预览 | 通过 |
| 问题工作区 | 严重级别/规则筛选、观测值、期望值、中文建议 | 通过 |
| 报告导出 | 复用 `atomic_write_report`，拒绝输入目录内目标 | 通过 |
| 只读回归 | Qt smoke test 对扫描前后文件 SHA-256 | 通过 |
| 自动验证 | 70 tests、Ruff、Schema/Capability/素材漂移门禁 | 通过 |
| 演示场景 | 16/0、12/5、58/0、14/3，全部 `ReadOnly=True` | 通过 |
| 安装产物 | `asset_delivery_organizer-0.2.0-py3-none-any.whl` | 通过 |
| 视觉验收 | 1440×900 四工作区、1080×680 窄窗口真实截图 | 通过 |

## 截图

- `docs/screenshots/workbench-setup.png`
- `docs/screenshots/workbench-files.png`
- `docs/screenshots/workbench-issues.png`
- `docs/screenshots/workbench-report.png`
- `docs/screenshots/workbench-narrow.png`

首轮截图发现无头 Qt 环境无法自动选择中文字体，随后增加 Windows 中文字体显式载入与应用级回退；复拍后中文正常显示。窄窗口复核后隐藏重复表格列并保留右侧证据检查器，避免通过缩小字体适配。

## 已知边界

- 当前是独立桌面工作台，不是 Maya/Unreal 内嵌面板；
- 不执行文件改名、移动、删除、格式转换或材质网络写入；
- 不维护供应商权限、项目周期或正式审核数据库；
- Profile 编辑器、dry-run 整理方案和薄 DCC 接入层属于后续里程碑。
