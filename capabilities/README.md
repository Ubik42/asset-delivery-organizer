# 机器可读能力清单

`asset-delivery-organizer.v1.json` 声明当前安装版本真实支持的能力：Profile/Report 合同、桌面/CLI/API 入口、五条规则及版本、扫描语义、只读审计约束、安全整理，以及可视化 Profile 编辑能力。

Profile 编辑部分明确声明：

- 两个版本化模板；
- 严格合同校验；
- 交付目录之外的原子保存；
- 禁止把 Profile 写进当前交付目录；
- Profile 变化后旧审计自动失效。

目录与格式规则明确声明 `path.allowed-roots@1.0.0` 的 `roots` 参数，以及 `file.allowed-extensions@1.0.0` 的 `extensions` 和可选 `ignored_roots` 参数。它们只使用稳定文件事实，不声称检查 DCC 场景内部内容。

配套 JSON Schema 描述能力清单协议。文件由运行时代码生成；正常验证使用 `python scripts/export_capabilities.py --check`，发现漂移即失败。安装后的环境也可以运行 `ado-capabilities` 获取同一份声明。
