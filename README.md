# 日文输入法（中文式选词）

跑在 Windows 上的日语输入法，交互习惯对齐中文拼音输入法：

- 输入罗马字**立即**显示假名和候选词窗口，不需要按空格进入转换
- **数字键 1-9 直接选词上屏**，空格上屏当前高亮候选
- **前缀联想**：打到一半就出以它开头的词（mozc 全量词典，73 万读音）
- **候选多于 9 个时：`,` 上一页、`.` 下一页**（`<` `>`、PageUp/PageDown 也行）；不足一页时 `,` `.` 仍是标点 `、` `。`
- ↑/↓ 移动候选高亮，Enter 上屏原始假名，Esc 取消，Backspace 回删
- 标点自动转换：`[` → `「`，`]` → `」`，`/` → `・`
- **Tab 上屏全角片假名**（`コーヒー`）；**`~ 键（Tab 左边）上屏半角片假名**（`ｺｰﾋｰ`）
- **单击 Shift 切换 日文/纯英文 模式**（光标旁弹出模式提示）；Shift+字母会把当前假名上屏后输入大写英文
- **用户学习**：选过的词下次排在前面（记录在 `%APPDATA%\jpime\user_history.json`）
- **快捷键全部可自定义**：托盘菜单 → 打开设置（「横排」「竖排」两个页签独立配置，竖排另含「确认选中候选」），或直接编辑 `%APPDATA%\jpime\config.json` 的 `keymap` / `keymap_vertical`（热重载）
- 注册为**独立的日语输入法**（ja-JP），与微软日文输入法并列
- 托盘只有一个图标（自绘菜单：设置 / 横竖排切换 / 重启后端 / 日志）；PIMELauncher 自带的托盘图标已打补丁去除
- 带正经卸载：系统"应用和功能"里可卸载，原版 PIME DLL 自动恢复

## 给新机器安装（最终用户）

1. 下载仓库 zip（Code → Download ZIP）解压，或 `git clone` 本仓库
2. 右键 `install.ps1` →「使用 PowerShell 运行」
3. 批准一次管理员权限（UAC），等待完成弹窗

脚本会联网下载大件：PIME 框架本体（GitHub release，失败自动走镜像）、便携 Python 3.12 运行时、MeCab / mozcpy 词典（PyPI）、mozc 词典文本（gitee 镜像，现场构建联想索引）；定制 DLL / PIMELauncher / 托盘程序等小二进制已随仓库自带（`bin/`）。脚本可重复运行，已装好的组件会自动跳过。装完在 日语 的键盘列表里启用「日文输入法（中文式选词）」。卸载走系统「应用和功能」。

## 架构

```
PIME (TSF 框架)  ──>  jp_ime.py (按键/候选窗交互, 跑在 PIME 自带 Python 3.8 里)
                          ├─ romaji.py           罗马字 -> 假名
                          ├─ user_history.py     用户学习（选词记忆）
                          └─ converter.py        ConverterProxy ──stdio JSON──> converter_server.py
                                                                                    ├─ MeCab + mozcpy 的 Mozc 词典（整句转换）
                                                                                    └─ predict_index.pkl（前缀联想）
                                        (helper 跑在便携 64 位 Python 运行时里)
```

- [PIME](https://github.com/EasyIME/PIME) 负责 Windows 文本服务框架（TSF）集成；候选窗渲染是改过的 libIME2（`PIME-src/`：圆角白底、灰底选中、DPI 感知高清渲染）
- 精确转换用 [mozcpy](https://github.com/ikegami-yukino/mozcpy) 的 Mozc 词典（MeCab 格式，支持整句 N-best）
- 前缀联想索引用 `build_predict_index.py` 从 mozc dictionary_oss 文本构建
- PIME 自带的 32 位 Python 3.8 装不了 MeCab 的轮子，所以转换引擎跑在独立 helper 进程里；helper 崩溃会自动重启，彻底不可用时退化为纯假名候选

## 开发

```bat
python -m venv .venv
.venv\Scripts\pip install mecab-python3 mozcpy pytest
.venv\Scripts\python -m pytest tests/ -q      :: 66 个单元测试
.venv\Scripts\python test_live.py             :: 真实环境协议测试（免管理员）
.venv\Scripts\python install.py               :: 部署到本机 PIME（自动提权）
```

定制二进制（`bin/`）如需更新：重编译 `PIME-src/` 后把 Release 产物复制过去并提交。

## 已知限制

- 候选窗样式修改在 `PIME-src/`（libIME2 + PIMETextService），重编译需要 VS 2022 Build Tools
- 没有配置界面；转换引擎无整句级别的上下文学习
