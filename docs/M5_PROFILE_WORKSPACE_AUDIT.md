# M5 项目 Profile 工作区验收

日期：2026-08-27

## 结论

M5-S1 已完成。普通审核人员可以从环境资产或角色资产模板建立项目 Profile，导入现有 `art-delivery-profile/1`，编辑项目身份与三条规则参数，查看中文字段级错误，并把有效配置原子保存到交付目录之外。应用新 Profile 或改变本次启用规则后，旧审计和旧整理计划立即失效，必须重新扫描。

## 直接证据

| 验收项 | 证据 | 结果 |
| --- | --- | --- |
| 无需手写 JSON | `environment-standard@1.0.0`、`character-standard@1.0.0` 两个模板 | 通过 |
| 严格导入与编辑 | Profile 草稿核心无 PySide6 依赖，保存后由原 CLI 加载器重读 | 通过 |
| 字段级错误 | Profile ID、版本、正则、格式、贴图通道、版本数和规则重复均有明确错误 | 通过 |
| 保存安全 | 交付目录内目标在写入前拒绝；已有目标默认不覆盖；外部写入采用原子替换 | 通过 |
| 旧状态失效 | Profile 摘要变化或规则选择变化会清空报告、整理计划和执行按钮 | 通过 |
| 自动测试 | 93 项通过，含 9 项 Profile 核心/模板测试和 3 项 Qt 工作台测试 | 通过 |
| 演示素材 | 4 组、100 个合成文件全部通过漂移校验，审计后保持只读 | 通过 |
| Windows 生命周期 | Profile 页面真实 Windows Qt 后端连续启动/退出两次，既有 Python PID 未受影响 | 通过 |
| 干净安装 | wheel 中模板构建、外部保存、CLI 重载和交付目录拒绝全部通过 | 通过 |
| 本轮 wheel | `asset_delivery_organizer-1.0.0-py3-none-any.whl`，SHA-256 `faaf5ce40d59095425cecea786bf96273833cba3dfc7ee4c8d4c0bbe679b0d8a` | 通过 |

M5 是 1.1 开发路线的功能切片，正式版本号和 Windows 分发仍由 M7 统一发布。

## 真实运行截图

- `docs/screenshots/workbench-profile-editor.png`：有效 Profile 与三条规则；
- `docs/screenshots/workbench-profile-invalid.png`：无效正则字段与禁用保存；
- `docs/screenshots/workbench-profile-save-rejected.png`：交付目录内保存被拒绝；
- `docs/screenshots/workbench-profile-narrow.png`：1080×680 窄窗口滚动布局。

机器可读 Windows 生命周期证据见 `docs/evidence/gui-lifecycle-m5-s1.json`。

## 保持的边界

- Profile 编辑不会修改交付资产；
- 模板是合成的通用示例，不冒充商业项目内部标准；
- 当前仍只配置三个已实现规则，不接受无法执行的未知规则；
- Maya/Unreal 场景、拓扑、材质网络和自动贴图生成仍不在本工程中冒充完成。
