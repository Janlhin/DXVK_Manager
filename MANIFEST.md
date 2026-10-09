# MANIFEST — 第三方来源登记

本文件登记本项目引入的第三方源码、二进制与运行时的来源与用途，作为《强制工程校验方案》中
「来源留痕」条款的单一真相源。每条记录应能在复现时核查。

> 说明：python-app 运行时为**核心层零第三方依赖**；GUI 与封面需要以下两个运行时库，
> 由使用者另行 `pip install`，不在仓库内分发。其精确版本 SHA256 应在安装后由
> `pip show <pkg>` / 对应 wheel 哈希补全登记。

| 来源 URL | 许可 | 用途 | 引入方式 | SHA256 / 版本 |
| --- | --- | --- | --- | --- |
| https://pypi.org/project/PySide6/ | LGPL-3.0 | Qt6 GUI（QML 界面层 `dxvk_toolkit/ui/`） | 运行时 `pip install PySide6` | 随安装版本，待登记 |
| https://pypi.org/project/Pillow/ | HPND | 封面图缩放/格式转换（`dxvk_toolkit/covers.py`） | 运行时 `pip install Pillow` | 随安装版本，待登记 |
| https://github.com/doitsujin/dxvk/blob/master/dxvk.conf | zlib | 内置参考配置 `assets/dxvk.conf`（配置生成器的唯一数据源） | 原文打包进仓库 `assets/` | 随上游版本，待登记 |
| https://github.com/artmakh/dxvk-version-mananger | MIT | 功能灵感来源（Electron 版，本项目未复制其代码，仅重实现行为） | 外部参考，不在本仓库 | —（见 `../node-app/`，未入库） |
| https://github.com/CamoMano/DXVK-Configurator | GPL-3.0 | 配置生成能力灵感来源（网页版，本项目未复制其代码） | 外部参考，不在本仓库 | —（见 `../web-configurator/`，未入库） |

## 复现脚本（一键核查）

```bash
python -m pip show PySide6 Pillow 2>/dev/null | grep -E "^(Name|Version):"
```

## 待补登记

- [ ] 安装后把 PySide6 / Pillow 的精确 wheel SHA256 回填上表。
- [ ] 每次升级 `assets/dxvk.conf` 时记录上游 commit/版本与哈希。
