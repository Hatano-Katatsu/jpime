# -*- coding: utf-8 -*-
"""快捷键自定义：动作 -> 按键 映射，配置文件热重载。

配置文件: %APPDATA%\\jpime\\config.json（首次运行自动生成默认配置）
格式:
{
  "keymap": {
    "commit_full_katakana": ["tab"],
    "commit_half_katakana": ["oem3"],
    ...
  }
}
按键名：小写字母/数字/符号用字符本身（如 "a", ",", "<"），
特殊键用名字（"tab" "return" "space" "escape" "back" "oem3" "prior" "next" 等，
对应 keycodes.py 里的 VK_*）。
"""
import json
import os

# 动作 -> 默认按键
DEFAULT_KEYMAP = {
    'commit_kana': ['return'],            # 上屏原始假名
    'cancel': ['escape'],                 # 取消
    'commit_full_katakana': ['tab'],      # 全角片假名
    'commit_half_katakana': ['oem3'],     # 半角片假名（`~ 键）
    'page_up': [',', '<', 'prior', 'left'],   # 候选上一页
    'page_down': ['.', '>', 'next', 'right'],  # 候选下一页
    'cursor_up': ['up'],                  # 候选光标
    'cursor_down': ['down'],
    'toggle_english': ['shift'],          # 单击切换英文模式
}

# 界面选项默认值（candPerRow: 9=横排，1=竖排；japanese_punct: 日文标点映射）
DEFAULT_UI = {
    'candPerRow': 9,
    'japanese_punct': True,
}

# 按键名 -> VK 码（keycodes.py 的 VK_* 去掉前缀小写）
_SPECIAL_KEYS = {
    'back': 0x08, 'tab': 0x09, 'return': 0x0D, 'shift': 0x10,
    'control': 0x11, 'escape': 0x1B, 'space': 0x20,
    'prior': 0x21, 'next': 0x22, 'end': 0x23, 'home': 0x24,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'oem3': 0xC0, 'oem_comma': 0xBC, 'oem_period': 0xBE,
}
for _i in range(12):  # f1-f12
    _SPECIAL_KEYS['f%d' % (_i + 1)] = 0x70 + _i

if 'APPDATA' in os.environ:
    _CONFIG_DIR = os.path.join(os.environ['APPDATA'], 'jpime')
else:
    _CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))


def _normalize_keys(keys):
    """把用户写的按键列表规范化：未知的多字符 token 按单字符拆开。

    比如用户写 "-="（微软拼音式写法）会被拆成 '-' 和 '=' 两个键，
    而不是当成一个永远不匹配的键名。
    """
    out = []
    for k in keys:
        k = str(k).lower()
        if len(k) > 1 and k not in _SPECIAL_KEYS:
            out.extend(list(k))
        else:
            out.append(k)
    return out


class Config:
    def __init__(self, path=None):
        self._path = path or os.path.join(_CONFIG_DIR, 'config.json')
        self._mtime = None
        self.keymap = dict(DEFAULT_KEYMAP)
        self.ui = dict(DEFAULT_UI)
        self.reload_if_changed(force=True)

    def reload_if_changed(self, force=False):
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if force or not os.path.exists(self._path):
                self._write_default()
            return
        if not force and mtime == self._mtime:
            return
        try:
            with open(self._path, encoding='utf-8') as fp:
                data = json.load(fp)
            custom = data.get('keymap', {})
            keymap = dict(DEFAULT_KEYMAP)
            for action, keys in custom.items():
                if action in keymap and isinstance(keys, list) and keys:
                    keymap[action] = _normalize_keys(keys)
            self.keymap = keymap
            ui = dict(DEFAULT_UI)
            try:
                per_row = int(data.get('candPerRow', DEFAULT_UI['candPerRow']))
                if 1 <= per_row <= 20:
                    ui['candPerRow'] = per_row
            except (TypeError, ValueError):
                pass
            ui['japanese_punct'] = bool(
                data.get('japanese_punct', DEFAULT_UI['japanese_punct']))
            self.ui = ui
            self._mtime = mtime
        except Exception:  # noqa: BLE001
            pass  # 配置损坏时用当前配置继续跑

    def _write_default(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as fp:
                json.dump({'keymap': DEFAULT_KEYMAP, **DEFAULT_UI}, fp,
                          ensure_ascii=False, indent=2)
            self._mtime = os.path.getmtime(self._path)
        except Exception:  # noqa: BLE001
            pass

    @property
    def cand_per_row(self):
        """候选窗每排个数：9=横排，1=竖排。"""
        return self.ui.get('candPerRow', DEFAULT_UI['candPerRow'])

    @property
    def japanese_punct(self):
        """日文标点映射开关（, -> 、 . -> 。 等）。"""
        return self.ui.get('japanese_punct', DEFAULT_UI['japanese_punct'])

    def match(self, key_event, action):
        """key_event 是否命中 action 绑定的任意按键。"""
        for key in self.keymap.get(action, []):
            if len(key) == 1:  # 字符键：按 charCode 匹配
                if key_event.charCode and chr(key_event.charCode) == key:
                    return True
            elif key in _SPECIAL_KEYS:
                if key_event.keyCode == _SPECIAL_KEYS[key]:
                    return True
        return False
