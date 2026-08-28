# 版本化 JSON 合同

这些 JSON Schema 由严格 Pydantic 模型生成并提交到仓库，使用者不需要在运行时定位兄弟工程。

- `art-delivery-profile.v1.schema.json`：项目 Profile 输入；
- `art-delivery-audit-report.v1.schema.json`：标准审计报告；
- `asset-delivery-organization-plan.v1.schema.json`：经过人工审阅的 dry-run 整理计划；
- `asset-delivery-organization-receipt.v1.schema.json`：整理收据和执行后复检身份。

有意修改合同时运行 `python scripts/export_contract_schemas.py` 和 `python scripts/export_organization_schemas.py`。固定验证入口使用 `--check`，模型与已提交 Schema 不一致时会失败。
