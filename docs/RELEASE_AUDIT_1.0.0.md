# 1.0.0 发布审计

日期：2026-08-25

范围：交付审计、人工批准整理、复检、历史与公开发布材料

## 结论

Asset Delivery Organizer 1.0.0 已形成可独立安装、可交互演示、可自动化调用的完整资产交付闭环。审计阶段严格只读；整理阶段必须先生成计划，完成路径、源哈希、重复操作和目标冲突预检，再由用户明确批准。执行失败会回滚已完成操作，成功后写入外部 JSON 收据并自动复检。

## 验收证据

| 验收项 | 证据 | 结果 |
| --- | --- | --- |
| 桌面产品 | 六个中文工作区：设置、文件、问题、整理、历史、报告 | 通过 |
| 审计内核 | 递归扫描、稳定文件事实、三条 Profile 规则、标准报告 | 通过 |
| 整理安全 | dry-run、路径约束、SHA-256 复核、冲突阻断、明确批准 | 通过 |
| 故障恢复 | 中途失败逆序回滚；缺失贴图仅提示，不自动伪造 | 通过 |
| 执行追踪 | 外部原子收据、执行后复检、SQLite 本机历史 | 通过 |
| 自动化接口 | `ado`、`ado-organize plan`、`ado-organize execute` | 通过 |
| 合同 | Profile、Report、Organization Plan、Receipt JSON Schema | 通过 |
| 自动测试 | 79 tests、Ruff、Goal/Schema/Capability/演示漂移门禁 | 通过 |
| 演示数据 | 4 个不可变场景、100 个合成文件、可变整理副本 | 通过 |
| Windows 生命周期 | 真实 Windows Qt 后端连续启动/退出两次，不终止既有 Python 进程 | 通过 |
| 安装产物 | `asset_delivery_organizer-1.0.0-py3-none-any.whl` | 通过 |
| 本轮安装包 SHA-256 | `13fb99833bc5111aae6d6848af53782ab546de5a30a76392c55916d1529d7aeb` | 通过 |

Windows 生命周期的机器可读证据见 `docs/evidence/gui-lifecycle-1.0.0.json`。

## 真实截图

- `docs/screenshots/workbench-setup.png`
- `docs/screenshots/workbench-files.png`
- `docs/screenshots/workbench-issues.png`
- `docs/screenshots/workbench-organization-plan.png`
- `docs/screenshots/workbench-collision-blocked.png`
- `docs/screenshots/workbench-organization-receipt.png`
- `docs/screenshots/workbench-report.png`
- `docs/screenshots/workbench-narrow.png`

截图由本仓库的合成交付数据和真实 PySide6 界面生成。冲突截图验证目标已存在时执行按钮被禁用；收据截图来自可变演示副本的真实整理与复检。

## 已知边界

- 工具不编辑 Maya、Unreal 或其他 DCC 场景内部数据；
- 不生成材质网络、不转换资产格式、不伪造缺失贴图；
- 本机历史用于独立工具审计追踪，不替代正式项目管理或权限系统；
- DCC 能力应通过后续薄接入层调用同一合同，而不是复制核心规则。
