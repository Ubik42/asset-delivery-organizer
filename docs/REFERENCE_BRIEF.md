# 需求来源：AutoSort_Tool

来源：`D:\Obsidian\3D\TA\工具TA.md` 中的公开项目描述。当前没有原工具源码；本工程只提取问题与交互思路，采用 clean-room 重新设计，不宣称复现其内部实现。

## 原描述中的需求

- 服务游戏/影视资产交付，覆盖文件管理、智能命名、材质网络、格式转换和项目记录；
- 供应商与审核角色记录公司/人员/项目/资产信息，维护 CSV 周期、版本和审核状态；
- 校验项目代码、资产类型、阶段等命名字段，并验证 Maya 版本和必需插件；
- 扫描 `.ma/.mb/.fbx/.obj/.usd/.abc` 与贴图，支持过滤、预览和元数据展示；
- 从场景名推导 mesh/material 命名，识别 UDIM 与 B/E/M/R/N/H 贴图语义；
- 构建 aiStandardSurface、shadingEngine、file、place2dTexture、bump2d 网络；
- 合并/独立导出、收集贴图、OBJ 与 FBX 批量转换并处理重名。

## 我们的修正

- 先实现 DCC 外核心，不为每个宿主复制完整插件；
- CSV 只是适配格式，核心使用版本化 JSON 模型；
- 文件更改必须 dry-run、冲突检查和复检；
- 材质 manifest 与 DCC 节点构建分层；
- 真实权限和制片管理留给正式项目管理系统。
