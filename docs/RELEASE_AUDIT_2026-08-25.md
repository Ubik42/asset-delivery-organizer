# 只读产品发布审计

日期：2026-08-25

版本：`0.1.0`

范围：最初授权的只读 Asset Delivery Organizer MVP 及 M1 稳定性加固

## 结论

授权范围全部具备直接代码、自动测试、生成协议和全新环境端到端证据。工具不依赖 DCC 或兄弟仓库，不修改被审计目录，也没有实现 UI、输入文件改名/移动、材质网络或多 DCC Adapter。

未来安全整理只是 `docs/DEVELOPMENT_PLAN.md` 中的候选路线，需要新的明确用户授权，不属于已完成 `/goal`。

## 原始要求—权威证据

| 要求 | 实现证据 | 验证证据 | 结论 |
| --- | --- | --- | --- |
| 读取 `art-delivery-profile/1` | `audit.load_profile` 与严格 `DeliveryProfile` | Profile 有效/错误/未知字段/重复规则测试；Schema 与 Skill 导出一致 | 通过 |
| 递归扫描指定目录 | `scanner.scan_delivery` | 嵌套目录、链接边界和稳定排序测试 | 通过 |
| 稳定文件事实 | portable relative path、SHA-256、大小、媒体类型、parsed tokens | 双次扫描、稳定 audit ID、扫描中变化失败测试 | 通过 |
| 三条指定规则 | `rules.py` 中三个 `1.0.0` evaluator | filename 错误、旧版本、缺失贴图以及有效交付测试 | 通过 |
| 输出 `art-delivery-audit-report/1` | 严格 `DeliveryAuditReport` 与流式标准 JSON | Schema 漂移门、协议往返、全新环境报告解析 | 通过 |
| 不修改输入 | 输入根写入拒绝、外部原子输出、`write_count=0` | 测试和发布审计均比较内容哈希、大小和 mtime | 通过 |
| 指定成功/失败/安全测试 | `tests/` 与 `scripts/tests/` | 固定门禁共 54 项通过 | 通过 |
| 安装、CLI、边界与计划 | `README.md`、能力清单、开发计划 | wheel 构建及全新环境真实 CLI 通过 | 通过 |

## 明确禁区审计

- 没有 UI 模块或前端依赖；
- 没有输入文件 rename、move、delete 实现；唯一 `os.replace` 只用于输入根外报告的原子提交；
- 没有材质网络写入；
- 没有 Maya、Unreal、Blender、Houdini 或 3ds Max SDK import；`.ma/.mb` 只作为媒体类型识别；
- 没有 `art_pipeline_skill` import、绝对兄弟仓路径或运行时定位逻辑；
- wheel 运行依赖只有 `pydantic>=2.11,<3`，pytest 与 Ruff 仅为 dev extra。

## 发布门结果

固定验证：

- Goal-state 语义审计：通过；
- Profile/Report Schema 漂移检查：通过；
- 能力清单漂移检查：通过；
- pytest：54 项通过；
- Ruff：通过。

全新环境审计：

- wheel：`asset_delivery_organizer-0.1.0-py3-none-any.whl`；
- 最终完成态复验 wheel SHA-256：`48183f2c1c47f71eeea986e129aa78e4d28c358f0f1de1c9cf629000f0f3d4ba`；
- Python：3.14.3；
- 模拟交付：4 个文件；
- 报告：3 个问题，分别来自 `filename.pattern`、`texture.required-channels`、`version.latest-only`；
- artifact 文件名等于 `<audit_id>.json`；
- `input_unchanged=true`、`write_count=0`、严格报告解析通过；
- 临时全新环境在审计结束后安全清理。

wheel 内部构建时间会影响归档字节，因此此哈希是本轮产物证据，不宣称跨构建可复现。发布审计可用 `scripts/release_audit.ps1` 重跑。
