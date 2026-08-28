# 1.1.0 发布审计

## 发行身份

- 产品版本：`1.1.0`；
- Windows 平台：Windows 10/11 x64；
- 便携包：`AssetDeliveryOrganizer-1.1.0-windows-x64.zip`；
- 便携包 SHA-256：`f71a313339041ba38d6710260f8618029d94c25a85283998ff3ea0f3077f61cf`；
- wheel：`asset_delivery_organizer-1.1.0-py3-none-any.whl`；
- wheel SHA-256：`516cc0f2b3365a7c6af98ec96615baa39967f9bebe2f3c194fb9063457054940`；
- 构建环境：Python 3.14.3、PySide6 6.11.2、PyInstaller 6.22.2；
- 公开仓库：`https://github.com/Ubik42/asset-delivery-organizer`；
- 公开 Release：`https://github.com/Ubik42/asset-delivery-organizer/releases/tag/v1.1.0`。

## 可重复构建入口

`scripts/build_windows_distribution.ps1` 重新构建四个入口、内置 Profile、五套演示、许可证、说明、排序后的 ZIP、内部 manifest 与外部 SHA-256。构建脚本只清理精确校验后的 `work/windows-build`，不触碰用户交付。

构建机 PATH 中存在 Poppler 的 ICU 78 DLL；它与 Qt6Core 使用的 Windows 系统 ICU ABI 不兼容。打包门禁先确认系统 ICU 存在，再从发行目录移除两项被误收集的构建机 DLL。脱离仓库的真实启动证明运行时使用系统 ICU，避免把本机污染带给用户。

## 独立运行证据

`docs/evidence/windows-portable-1.1.0.json` 记录：

- ZIP 解压到系统临时目录，清除 `PYTHONHOME` 与 `PYTHONPATH`；
- Windows ProductVersion、CLI 与能力清单全部为 1.1.0；
- 五套内置场景的文件数、问题数、规则分布与只读快照全部匹配；
- 在可变副本生成并执行 3 项整理，复检剩余 2 个缺失贴图问题；
- 真实 Windows GUI 启动两次，只等待并关闭自己创建的 PID；
- 预置 1.0 `history.sqlite3` 的审计行被完整保留；
- 历史数据库位于程序与交付目录之外；
- 临时验收目录在连接和进程全部关闭后正常删除。

`docs/screenshots/workbench-portable-success.png` 由打包后的 EXE 真实生成，其余 6 张当前规则截图由 1.1.0 源码入口生成并人工查看。

## 干净 wheel 与自动化门禁

干净虚拟环境安装 wheel 后，Profile 编写、保存边界、五条规则、输入只读、报告合同、安全整理与复检收据全部通过。快速门禁包含测试、Ruff、五场景演示漂移验证、goal 状态审计与秘密扫描。

## 限制与安全声明

当前 ZIP 未商业代码签名，因此不声称“无 SmartScreen 提示”。审计严格只读；整理必须 dry-run、冲突检查、精确批准、失败回滚与执行后复检。产品不解析 DCC 场景内部内容，也不自动补贴图、转格式、删除或静默覆盖文件。
