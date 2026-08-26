# 持续开发循环

每轮先运行 `scripts/goal.ps1 -Action Resume` 和 `-Action Doctor`，读取 `config/goal-state.json`、最后 checkpoint、当前 Git 状态和代码事实。若状态与代码冲突，先修正状态。

实现仅限 `nextSlice.allowedPaths`，遵守 non-goals。完成当前切片必须运行固定的 `scripts/validate.ps1 -Tier quick`，并覆盖成功、失败与安全路径；通过后才增加 `stateRevision`、写入下一个顺序 checkpoint，并推进唯一下一切片。

一次失败不等于阻塞。先做只读诊断和安全降级；只有不可绕过的同一条件持续存在时才能将目标标记为 blocked，并明确恢复条件。
