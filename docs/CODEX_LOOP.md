# `/goal` 持续开发循环

## 1. 恢复上下文

```powershell
.\scripts\goal.ps1 -Action Resume
.\scripts\goal.ps1 -Action Doctor
git status --short
```

随后读取状态、最后 checkpoint 和当前切片直接相关文件。不要从 README 的宣传文案推断实现事实；以代码、测试和实际运行证据为准。

## 2. 建立本轮切片合同

复述并检查：

- `outcome`：本轮结束后用户具体能完成什么；
- `risk`：R0 文档、R1 只读、R2 外部写入、R3 输入变更、R4 不可恢复/外部系统；
- `allowedPaths`：本轮可修改范围；
- `nonGoals`：主动不做什么；
- `acceptance`：必须能由测试、截图、报告或真实运行直接证明。

如果合同无法支撑完整黄金路径，应先修改 goal state 并写 checkpoint，不能私下扩大范围。

## 3. 实现顺序

```text
失败与安全合同
→ 可脱离 UI 的业务核心
→ 单元/集成测试
→ 中文 UI 与交互状态
→ 合法演示素材
→ 实际运行截图
→ README、教程和发布证据
```

文件写入功能必须额外经过：

```text
预览 → 全量预检 → 明确批准 → 执行 → 失败回滚 → 复检 → 外部收据
```

## 4. 固定验证

最低门禁：

```powershell
.\scripts\validate.ps1 -Tier quick
```

涉及演示素材时增加：

```powershell
.\demo\run-demo.ps1 -Verify
```

涉及桌面 UI 或发布时增加真实 Windows 生命周期与干净 wheel 安装审计。验证入口必须写死在仓库脚本中；禁止读取状态字符串后动态执行。

## 5. 推进状态

只有 acceptance 全部满足后：

1. `stateRevision + 1`；
2. 新建下一个连续编号 checkpoint；
3. 把当前 slice 结果写为可核查 evidence；
4. 只保留一个 in-progress milestone 和一个 nextSlice；
5. 再运行 Doctor，确认状态机闭合。

目标完成时使用 `status: complete`，并把 `currentMilestone` 与 `nextSlice` 设为 `null`。禁止使用 `completed` 等 Schema 外状态。阻塞态保留当前 milestone 与恢复切片，并写清恢复条件。
