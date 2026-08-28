# Asset Delivery Organizer 演示录制脚本

目标成片 13–15 分钟，完整展示“从模板建立项目规则，收到供应商交付，检查目录与格式边界，记录项目上下文，审计，定位证据，生成整理计划，拦截冲突，批准执行，复检并查看收据”。

## 录制前准备

```powershell
cd D:\3D\_tools\asset-delivery-organizer
.\.venv\Scripts\python.exe -m pip install -e ".[ui,dev]"
.\demo\run-demo.ps1 -Reset -Verify
.\demo\prepare-organization-demo.ps1
.\.venv\Scripts\ado-ui.exe
```

建议 1920×1080、显示缩放 100% 或 125%，关闭个人通知。演示只操作 `work\organization-demo`，不要直接整理 `demo/scenarios`。

## 镜头 1：真实问题，约 45 秒

展示可变副本中的 Meshes、Textures 和供应商说明。说明常见交付风险：错误命名、旧版本、缺失贴图，以及批量改名本身造成的覆盖风险。

## 镜头 2：项目规则模板，约 90 秒

进入“项目规则”，展示环境资产和角色资产两个版本化模板。点击“从模板新建”，说明允许目录、允许格式、格式忽略目录、命名正则、贴图通道和保留版本数都可以由审核人员配置，不必手写 JSON。

把允许目录临时改成 `Meshes, ../escape`，展示红色字段错误和禁用的保存按钮；恢复正确目录。强调 Profile 只能保存到交付目录之外，应用新 Profile 后旧审计与旧整理计划会失效。

## 镜头 3：交付上下文，约 60 秒

在“交付设置”填写审核角色、公司/人员代码、项目 atlas、资产 supplier-drop、阶段审核、状态待复核。选择 Profile 和五条规则。

重点：这不是一条固定命令，审核人员可以决定本次规则范围，审计记录保留负责人和状态。

## 镜头 4：目录与格式预检，约 75 秒

扫描 `05_delivery_boundary_preflight`，展示 9 个文件、4 个错误。先只筛选“交付目录白名单”，查看 `Exports` 的观测目录和允许目录；再筛选“交付格式白名单”，查看 `.blend` 的观测扩展名和允许格式。指出 `Documentation/vendor_brief.docx` 因忽略目录配置而不会误报。

## 镜头 5：命名、版本与贴图证据，约 90 秒

执行扫描，展示 12 个文件、5 个问题。依次查看：

- `SM_TempleGate_v001.fbx` 的版本观测值 1、期望值 3；
- `temple-gate-final.fbx` 的命名错误；
- `T_BrokenStatue_B.1001.png` 的缺失通道。

## 镜头 6：文件和贴图预览，约 60 秒

在文件浏览中选择贴图、仅有问题，搜索 `BrokenStatue`。展示缩略图、asset/channel/UDIM 解析和 SHA-256；再打开供应商文本说明。

## 镜头 7：整理计划，约 90 秒

选择外部输出目录，生成 3 项计划。解释：

- 旧版本归档到输入目录之外；
- 错误命名建议可以人工编辑；
- 缺失贴图不会被自动伪造；
- 每项操作都可以取消。

## 镜头 8：冲突拦截，约 60 秒

把重命名目标改成已有的 `SM_BrokenStatue_v004.fbx`。展示底部“目标已经存在”以及禁用的执行按钮。恢复正确目标后预检重新通过。

## 镜头 9：批准与执行，约 60 秒

点击“批准并执行整理”，展示明确确认框。说明执行前还会重新核对所有源 SHA-256 和目标状态；任何中途失败都会逆序回滚。

## 镜头 10：复检与历史，约 90 秒

执行完成后自动进入审计记录：

- 整理前：12 文件、5 问题；
- 整理后：10 文件、2 问题；
- 收据：3 项操作、复检问题 2、外部 JSON 路径。

打开输出目录，展示两个归档旧版本和 receipt；返回交付目录，展示规范化文件名。

## 镜头 11：自动化合同，约 60 秒

在终端展示 `ado`、`ado-organize plan` 和必须精确填写 plan ID 的 `ado-organize execute`。运行：

```powershell
.\scripts\validate.ps1 -Tier quick
.\demo\run-demo.ps1 -Verify
```

展示全部测试通过和五个不可变场景 `ReadOnly=True`。

## 收尾，约 30 秒

说明当前边界：这是完整的独立资产交付工具，桌面/CLI/API 共用核心；它不冒充 Maya 材质网络、多 DCC 内嵌面板或在线项目管理系统。DCC 场景能力以后通过薄 Adapter 接入。
