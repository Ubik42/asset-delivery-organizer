# Asset Delivery Organizer 1.1.0

1.1.0 是首个面向普通 Windows 用户的免 Python 可移植发行版。

## 主要变化

- 新增可视化项目 Profile 工作区：模板新建、导入、即时校验、原子另存与应用；
- 新增交付目录白名单与文件格式白名单，现有五条规则都可由 Profile 配置；
- 演示扩展为 5 组、109 个确定性合成文件；
- 提供独立中文桌面程序、只读审计 CLI、安全整理 CLI 与能力清单 CLI；
- 完成脱离源码/系统 Python 的五场景审计、两次 GUI 生命周期、整理闭环与 1.0 历史升级验证。

## 下载

- `AssetDeliveryOrganizer-1.1.0-windows-x64.zip`
- `AssetDeliveryOrganizer-1.1.0-windows-x64.zip.sha256`
- `asset_delivery_organizer-1.1.0-py3-none-any.whl`

Windows ZIP SHA-256：`f71a313339041ba38d6710260f8618029d94c25a85283998ff3ea0f3077f61cf`

Python wheel SHA-256：`516cc0f2b3365a7c6af98ec96615baa39967f9bebe2f3c194fb9063457054940`

## 已知边界

- 发行物尚未商业代码签名，Windows 可能提示未知发布者；
- 不解析 Maya/Unreal 场景内部拓扑、材质网络或引用；
- 不自动生成缺失贴图，不做格式转换，不静默覆盖或删除文件；
- 整理只覆盖当前确定性改名与旧版本外部归档。
