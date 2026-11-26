## 变更摘要

<!-- 本次改了什么：哪个模块 / 哪份文档，为什么改。 -->

## 验证命令与证据

<!-- 本地跑过的检查命令与结果，例如：
python -m pip install -r requirements-dev.txt
.\verify.ps1   （或 bash verify.sh）
python -m pytest tests -q
未安装 PySide6 导致的跳过请如实标注。 -->

## CI 结果

<!-- 填写 CI 工作流名称与结论（通过 / 未触发 / 无 runner）；未跑的检查不要写“通过”。 -->

## 风险与回滚

- 风险：<!-- 可能影响的范围（游戏检测 / 下载安装 / 配置生成 / 界面） -->
- 回滚：未合并时关闭本 PR 即可，影响面为 0；合并后用 `git revert <commit>` 撤销。
