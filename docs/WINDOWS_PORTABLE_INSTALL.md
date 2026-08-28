# Windows 可移植版安装、升级与卸载

## 系统要求

- Windows 10/11 64 位；
- 建议 1920×1080，显示缩放 100%–150%；
- 不需要安装 Python，也不需要克隆源码仓库；
- 约 250 MB 可用磁盘空间（含解压空间与本机历史）。

## 首次安装

1. 从 GitHub Releases 下载 `AssetDeliveryOrganizer-1.1.0-windows-x64.zip` 和同名 `.sha256`；
2. 用 `Get-FileHash .\AssetDeliveryOrganizer-1.1.0-windows-x64.zip -Algorithm SHA256` 核对值为 `f71a313339041ba38d6710260f8618029d94c25a85283998ff3ea0f3077f61cf`；
3. 完整解压到有写权限的位置，例如 `D:\Tools\AssetDeliveryOrganizer-1.1.0`；
4. 双击 `AssetDeliveryOrganizer.exe`，不要直接在 ZIP 内运行；
5. 先选择内置 `demo\scenarios\05_delivery_boundary_preflight` 与 `profiles\atlas.environment.delivery.json`，扫描结果应为 9 个文件、4 个错误。

本发行物没有商业代码签名。Windows 可能显示“未知发布者”；请只从本项目公开 Release 下载并核对 SHA-256。工具不会要求管理员权限。

## 升级 1.0 → 1.1

1. 关闭所有程序窗口；
2. 把 1.1 解压到一个新的应用文件夹；
3. 直接启动 1.1，不要把新旧程序文件混合覆盖；
4. 本机审计历史默认位于用户数据目录，不在程序或交付目录中，1.1 会复用 1.0 的 `history.sqlite3`；
5. 确认历史页数据正常后再删除旧应用文件夹。

可用环境变量 `ADO_DATA_DIR` 为团队测试指定独立数据目录。默认位置由 Qt 的用户数据目录规则决定。Profile、报告、归档与收据仍应由用户选择交付目录之外的位置。

## 卸载与数据保留

关闭程序后删除整个应用文件夹即可卸载。卸载不会静默删除 `history.sqlite3`，避免误丢审计记录；如确实要彻底清理，请先备份，再删除用户数据目录。工具不会把历史数据库写进被审计的交付目录。

## 命令行入口

- `ado.exe`：只读审计并输出标准 JSON；
- `ado-organize.exe`：生成 dry-run 方案，只有精确批准 plan ID 后才执行；
- `ado-capabilities.exe`：输出机器可读能力清单。

完整操作见 [中文使用教程](USER_GUIDE.md)，录屏流程见 [演示录制脚本](VIDEO_TUTORIAL.md)。
