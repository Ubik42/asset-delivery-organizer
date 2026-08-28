# 可录屏演示素材

这里保存 5 组确定性生成的合成美术交付，共 109 个文件：包含可预览的 128×128 PNG 贴图、ASCII FBX、USDA 内容的 `.usd` 文件、供应商说明，以及用于规则验证的 `.blend/.psd/.docx` 合成占位文件。

素材模拟真实的目录、命名、版本、UDIM 和多供应商关系，但不包含任何公司或商业项目资产。全部由 `scripts/generate_demo_assets.py` 从固定算法生成，可作为 CC0-1.0 测试夹具重新分发。

## 场景目录

| 场景 | 文件 | 预期问题 | 演示重点 |
| --- | ---: | ---: | --- |
| `01_clean_environment_delivery` | 16 | 0 | 合规命名、完整 B/N/R、TempleGate 双 UDIM |
| `02_supplier_drop_with_issues` | 12 | 5 | 错误命名 1、缺失贴图 2、旧版本 2 |
| `03_multi_asset_udim_batch` | 58 | 0 | 8 个资产、48 张 UDIM 贴图、批量稳定扫描 |
| `04_nested_multi_vendor_batch` | 14 | 3 | 递归供应商目录、错误命名、旧版本、缺 R |
| `05_delivery_boundary_preflight` | 9 | 4 | 错放到 Exports/Temp、禁用 .blend/.psd、忽略 Documentation 格式 |

精确结果保存在 `expected-results.json`；每个素材的路径、大小和 SHA-256 保存在 `assets-manifest.json`。

## 图形界面演示

在仓库根目录运行：

```powershell
.\.venv\Scripts\ado-ui.exe
```

只读检查可直接使用五个场景。需要演示重命名与归档时，必须先准备可变副本：

```powershell
.\demo\prepare-organization-demo.ps1
```

工具会把 `02_supplier_drop_with_issues` 复制到被 Git 忽略的 `work/organization-demo/supplier-drop`，逐文件验证 SHA-256，并把 `work/organization-demo/output` 作为外部归档/收据目录。整理演示不得直接操作 `demo/scenarios`。详细步骤见 [VIDEO_TUTORIAL.md](../docs/VIDEO_TUTORIAL.md)。

“项目规则”工作区直接复用这些合法合成素材：先导入 `profiles/atlas.environment.delivery.json` 展示五条真实规则，再从环境/角色模板新建草稿。模板示例位于 `profiles/presets`，自动测试会校验其与运行时模板没有漂移。

## 一键自动验证

在仓库根目录运行：

```powershell
.\demo\run-demo.ps1 -Verify
```

脚本会：

1. 校验 109 个输入素材的字节内容；
2. 依次运行与图形界面共用核心的 5 个真实 CLI 审计；
3. 把报告写到被忽略的 `demo/output`；
4. 对照预期文件数、严重级别和规则计数；
5. 再次校验全部输入，证明工具没有修改素材。

恢复确定性初始素材：

```powershell
.\demo\run-demo.ps1 -Reset -Verify
```

`-Reset` 调用的是演示夹具生成器，并把 `demo/scenarios` 视为完全托管的生成目录：其中手动加入的文件会被清除。它不是产品的文件整理能力，Asset Delivery Organizer 本身依旧严格只读。

完整录制流程见 [VIDEO_TUTORIAL.md](../docs/VIDEO_TUTORIAL.md)，录制时可单独打开 [RECORDING_CHEATSHEET.md](RECORDING_CHEATSHEET.md)。
