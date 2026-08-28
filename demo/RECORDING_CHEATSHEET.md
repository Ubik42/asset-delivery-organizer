# 录屏速查卡

完整旁白和镜头设计见 `docs/VIDEO_TUTORIAL.md`；录制时只需把本页放在第二屏。

## 开场前

```powershell
cd D:\3D\_tools\asset-delivery-organizer
.\.venv\Scripts\python.exe -m pip install -e ".[ui,dev]"
.\demo\run-demo.ps1 -Reset -Verify
.\demo\prepare-organization-demo.ps1
.\.venv\Scripts\ado-ui.exe
```

预期：五行 `PASS`，文件/问题分别为 `16/0`、`12/5`、`58/0`、`14/3`、`9/4`。

## 界面主线

1. 项目规则：目录/格式白名单、环境/角色模板、危险目录阻断、另存到交付目录之外；
2. `05_delivery_boundary_preflight`：五条规则全开，筛选目录与格式问题，预期 9/4；
3. 问题审查：依次展示旧版本、错误命名、缺失贴图；
4. 文件浏览：选择贴图、仅有问题，搜索 `BrokenStatue`；
5. `01_clean_environment_delivery`：预期 16/0；
6. `03_multi_asset_udim_batch`：预期 58/0；
7. 整理方案：3 项操作、2 项缺失依赖；演示目标冲突被禁用；
8. 批准执行后：预期 10/2，历史中出现 3 项操作的外部收据；
9. 报告导出：先演示输入目录内被拒绝，再保存到 `work\organization-demo\output`。

## 干净交付

```powershell
ado .\demo\scenarios\01_clean_environment_delivery --profile .\profiles\atlas.environment.delivery.json --output .\demo\output\01_clean.audit.json
$clean = Get-Content .\demo\output\01_clean.audit.json -Raw | ConvertFrom-Json
$clean.summary | Format-List
```

## 问题交付

```powershell
ado .\demo\scenarios\02_supplier_drop_with_issues --profile .\profiles\atlas.environment.delivery.json --output .\demo\output\02_faulty.audit.json --fail-on-issues
$LASTEXITCODE
$faulty = Get-Content .\demo\output\02_faulty.audit.json -Raw | ConvertFrom-Json
$faulty.issues | Select-Object severity,rule_id,affected_file,message | Format-Table -Wrap
```

预期：退出码 `2`；5 个问题 = blocker 2、error 1、warning 2。

## 多 UDIM 与嵌套供应商

```powershell
ado .\demo\scenarios\03_multi_asset_udim_batch --profile .\profiles\atlas.environment.delivery.json --output .\demo\output\03_batch.audit.json
ado .\demo\scenarios\04_nested_multi_vendor_batch --profile .\profiles\atlas.environment.delivery.json --output .\demo\output\04_vendors.audit.json
```

## 只读安全镜头

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_demo_assets.py --check
ado .\demo\scenarios\01_clean_environment_delivery --profile .\profiles\atlas.environment.delivery.json --output .\demo\scenarios\01_clean_environment_delivery\forbidden.json
$LASTEXITCODE
```

预期：109 个素材校验通过；危险输出退出码 `1`；没有生成 `forbidden.json`。

## 收尾

```powershell
ado-capabilities
.\demo\run-demo.ps1 -Verify
```

最后画面停在五行 PASS 和 `ReadOnly=True`。
