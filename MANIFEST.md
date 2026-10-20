# MANIFEST — 第三方来源登记

本文件登记本项目引入的第三方源码、二进制与运行时的来源与用途，作为《强制工程校验方案》中
「来源留痕」条款的单一真相源。每条记录应能在复现时核查。

> 说明：python-app 运行时为**核心层零第三方依赖**；GUI 与封面需要以下两个运行时库，
> 由使用者另行 `pip install`，不在仓库内分发。其精确版本 SHA256 应在安装后由
> `pip show <pkg>` / 对应 wheel 哈希补全登记。

| 来源 URL | 许可 | 用途 | 引入方式 | SHA256 / 版本 |
| --- | --- | --- | --- | --- |
| https://pypi.org/project/PySide6/ | LGPL-3.0 | Qt6 GUI（QML 界面层 `dxvk_toolkit/ui/`） | 运行时 `pip install PySide6>=6.4` | **6.12.0**（开发环境实测；见复现脚本） |
| https://pypi.org/project/Pillow/ | HPND | 封面图缩放/格式转换（`dxvk_toolkit/covers.py`） | 运行时 `pip install Pillow>=9.0` | **12.3.0**（开发环境实测；见复现脚本） |
| https://github.com/doitsujin/dxvk/blob/master/dxvk.conf | zlib | 内置参考配置 `assets/dxvk.conf`（配置生成器的唯一数据源） | 原文打包进仓库 `assets/` | SHA256 `60edaec2…fcd6759ad`（30,673 B，2026-10-20 核对） |
| https://github.com/doitsujin/dxvk | — | `assets/dxvk.conf.zh.json`（中文选项说明覆盖层，基于上游注释翻译） | 仓库内生成 | SHA256 `d57091d1…c64555be14`（16,221 B，2026-10-20 核对） |
| https://github.com/artmakh/dxvk-version-mananger | MIT | 功能灵感来源（Electron 版，本项目未复制其代码，仅重实现行为） | 外部参考，不在本仓库 | —（见 `../node-app/`，未入库） |
| https://github.com/CamoMano/DXVK-Configurator | GPL-3.0 | 配置生成能力灵感来源（网页版，本项目未复制其代码） | 外部参考，不在本仓库 | —（见 `../web-configurator/`，未入库） |

## 复现脚本（一键核查）

```bash
python -m pip show PySide6 Pillow 2>/dev/null | grep -E "^(Name|Version):"
sha256sum assets/dxvk.conf assets/dxvk.conf.zh.json
```

实测输出（版本 2026-10-09，资源哈希 2026-10-20）：
```
Name: PySide6
Version: 6.12.0
Name: pillow
Version: 12.3.0
60edaec21f8e164b1cad1568d4517442cce70c2c9ebef5465155289fcd6759ad  assets/dxvk.conf
d57091d1ca2dc16ee2222385c950c954394901738ac0fea1e67607c64555be14  assets/dxvk.conf.zh.json
```

## 已登记

- [x] PySide6 / Pillow 精确版本已登记（随安装版本，requirements.txt 约束下限）。
- [x] `assets/dxvk.conf` 与中文覆盖层的当前字节数与 SHA256 已按实际文件核对（2026-10-20）。
- [ ] 每次升级 `assets/dxvk.conf` 时记录上游 commit/版本与哈希。
