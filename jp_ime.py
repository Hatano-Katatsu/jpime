#! python3
# -*- coding: utf-8 -*-
r"""中文式交互的日语输入法 — PIME 模块。

交互设计（对齐中文拼音输入法习惯）：
- 输入罗马字立即显示假名 + 候选词窗口
- 数字键 1-9 直接选词上屏
- 空格上屏当前高亮候选（默认第一个）
- Enter 上屏原始假名，Esc 清空，Backspace 回删
- 日文标点映射（可在 config.json 用 japanese_punct 关闭）：
  , -> 、  . -> 。  [ -> 「  ] -> 」  / -> ・  ? -> ？  ! -> ！
  ( -> （  ) -> ）  : -> ：  ; -> ；  ~ -> 〜  \ -> ¥  @ -> ＠
  组字中按标点 = 上屏首选候选 + 标点；空闲时直接上屏标点
"""
import os.path
import sys

from keycodes import *  # for VK_XXX constants
from textService import *

# PIME 以 input_methods.jpime.jp_ime 包形式加载本模块，
# 同级模块（romaji/converter）需要显式把本目录加入搜索路径。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from romaji import RomajiConverter, hira_to_half_kata, hira_to_kata, kana_for_conversion  # noqa: E402
from converter import create_converter  # noqa: E402
from user_history import UserHistory  # noqa: E402
from config import Config  # noqa: E402

import threading as _threading  # noqa: E402

# 转换引擎全局单例：PIME 每个应用创建一个 TextService 实例，
# 若每实例各起一个 helper 进程，则每个应用的首字都要冷启动（约 800ms
# 词典+索引加载）。单例后整个后端只有一个 helper，只冷启动一次。
_CONVERTER = None
_CONVERTER_LOCK = _threading.Lock()


def _get_converter():
    global _CONVERTER
    if _CONVERTER is None:
        with _CONVERTER_LOCK:
            if _CONVERTER is None:
                _CONVERTER = create_converter()
    return _CONVERTER


def _prewarm_converter():
    try:
        _get_converter().candidates('ああ')
    except Exception:  # noqa: BLE001
        pass


# 模块加载即在后台预热（拉起 helper、预载词典与联想索引），
# 用户打到第一个字时引擎已经热了。
_threading.Thread(target=_prewarm_converter, daemon=True).start()

_SEL_KEYS = "123456789"
_PAGE_SIZE = 9          # 每页候选数
_MAX_PAGES = 5          # 最多 5 页（<> 翻页）

_PUNCT_MAP = {
    ',': '、',
    '.': '。',
    '[': '「',
    ']': '」',
    '/': '・',
    '?': '？',
    '!': '！',
    '(': '（',
    ')': '）',
    ':': '：',
    ';': '；',
    '~': '〜',    # U+301C WAVE DASH
    '\\': '¥',   # U+00A5 YEN SIGN
    '@': '＠',
    # < > 不映射：翻页/原样
}


class JpTextService(TextService):
    def __init__(self, client):
        TextService.__init__(self, client)
        self.icon_dir = os.path.abspath(os.path.dirname(__file__))
        self.romaji = RomajiConverter()
        self.converter = _get_converter()
        self.history = UserHistory()
        self.config = Config()
        self.english_mode = False   # Shift 单击切换 日文/纯英文
        self._shift_alone = False   # Shift 按下后是否还没碰过其它键
        self._all_cands = []        # 全部候选（分页前）
        self._page = 0
        self._applied_per_row = None  # 已应用到候选窗的每排个数

    def onActivate(self):
        TextService.onActivate(self)
        # 对齐微软拼音：12pt、Yu Gothic UI；每排个数可配置（9=横排，1=竖排）
        self._applied_per_row = self.config.cand_per_row
        self.customizeUI(candFontName='Yu Gothic UI',
                         candFontSize=12,
                         candPerRow=self._applied_per_row,
                         candUseCursor=True)
        self.setSelKeys(_SEL_KEYS)

    def _set_english_mode(self, english):
        self.english_mode = english
        self.showMessage('英文模式' if english else '日文模式', 2)

    # ---- 内部工具 ----

    def _buffer(self):
        return ''.join(self.romaji.buf)

    def _display_kana(self):
        """当前缓冲对应的假名（尾部挂起 n 转为 ん，其余未完成尾巴保留）。"""
        disp = self.romaji.display()
        if disp.endswith('n') and len(disp) > 1:
            disp = disp[:-1] + 'ん'
        elif disp == 'n':
            disp = 'ん'
        return disp

    def _refresh(self):
        """根据当前罗马字缓冲刷新 composition 和候选窗。"""
        if not self.romaji:
            self._clear()
            return
        disp = self.romaji.display()
        self.setCompositionString(disp)
        self.setCompositionCursor(len(disp))
        cands = self.converter.candidates(self._buffer(), limit=_PAGE_SIZE * 5)
        cands = self.history.rerank(kana_for_conversion(self._buffer()), cands)
        self._all_cands = cands
        self._page = 0
        self._show_page()

    def _show_page(self):
        start = self._page * _PAGE_SIZE
        page_cands = self._all_cands[start:start + _PAGE_SIZE]
        self.setCandidateList(page_cands)
        self.setCandidateCursor(0)
        self.setShowCandidates(bool(page_cands))

    def _turn_page(self, delta):
        """<>翻页，循环。"""
        if not self._all_cands:
            return
        pages = max(1, (len(self._all_cands) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._page = (self._page + delta) % pages
        self._show_page()

    def _clear(self):
        self.romaji.clear()
        self._all_cands = []
        self._page = 0
        self.setCompositionString('')
        self.setShowCandidates(False)
        self.setCandidateList([])

    def _commit(self, s):
        if not s:
            return
        self.romaji.clear()
        self._all_cands = []
        self._page = 0
        self.setCompositionString('')
        self.setShowCandidates(False)
        self.setCandidateList([])
        self.setCommitString(s)

    def _commit_candidate(self, idx):
        """idx 是全部候选里的全局下标。"""
        if 0 <= idx < len(self._all_cands):
            cand = self._all_cands[idx]
            # 用户学习：记住这个读音选了这个词
            self.history.record(kana_for_conversion(self._buffer()), cand)
            self._commit(cand)
        elif self.romaji:
            self._commit(self._display_kana())

    def _current_global_index(self):
        return self._page * _PAGE_SIZE + self.candidateCursor

    # ---- 按键处理 ----

    def checkConfigChange(self):
        # 每次消息都检查配置文件 mtime，热重载快捷键和候选窗排列
        self.config.reload_if_changed()
        per_row = self.config.cand_per_row
        if per_row != self._applied_per_row:
            self._applied_per_row = per_row
            self.customizeUI(candPerRow=per_row, candUseCursor=True)

    def _is_toggle_key(self, keyEvent):
        return self.config.match(keyEvent, 'toggle_english')

    def filterKeyDown(self, keyEvent):
        # 模式切换键本身要拦（单击切换 日文/英文 模式）
        if self._is_toggle_key(keyEvent):
            self._shift_alone = True
            return True
        self._shift_alone = False
        # Ctrl/Alt 组合键一律不拦
        if keyEvent.isKeyDown(VK_CONTROL) or keyEvent.isKeyDown(VK_MENU):
            return False
        # 英文模式：其余键全部放行
        if self.english_mode:
            return False
        # Shift+字母：先把当前缓冲按假名上屏，然后放行（输入大写英文）
        if keyEvent.isKeyDown(VK_SHIFT) and self.romaji:
            if ord('A') <= keyEvent.charCode <= ord('Z'):
                self._commit(self._display_kana())
                return False
        if self.romaji or self.showCandidates:
            return True  # 组字中：按键全部交给我们处理
        # 空闲时拦小写字母（开始新的组字）和日文标点（直接上屏映射标点）
        if ord('a') <= keyEvent.charCode <= ord('z'):
            return True
        return (self.config.japanese_punct and bool(keyEvent.charCode)
                and chr(keyEvent.charCode) in _PUNCT_MAP)

    def filterKeyUp(self, keyEvent):
        return self._is_toggle_key(keyEvent)

    def onKeyUp(self, keyEvent):
        # 切换键单独点击（中间没碰其它键）-> 切换 日文/英文 模式
        if self._is_toggle_key(keyEvent) and self._shift_alone:
            self._shift_alone = False
            if self.romaji:
                self._commit(self._display_kana())
            self._set_english_mode(not self.english_mode)
            return True
        return False

    def onKeyDown(self, keyEvent):
        ch = keyEvent.charCode
        code = keyEvent.keyCode
        cfg = self.config

        if cfg.match(keyEvent, 'toggle_english'):
            return True  # 已在 filterKeyDown 里标记，抬起时才切换

        if self.english_mode:
            return False

        if self.romaji:
            # 片假名转换（键位可在 config.json 自定义）
            if cfg.match(keyEvent, 'commit_full_katakana'):
                self._commit(hira_to_kata(self._display_kana()))
                return True
            if cfg.match(keyEvent, 'commit_half_katakana'):
                self._commit(hira_to_half_kata(self._display_kana()))
                return True
            # 数字键选词（选当前页的第 N 个；超出范围直接吞掉，不做任何其它事）
            if ord('1') <= ch <= ord('9') and self.showCandidates:
                idx = self._page * _PAGE_SIZE + ch - ord('1')
                if idx < len(self._all_cands):
                    self._commit_candidate(idx)
                return True
            # 空格：上屏高亮候选（无候选则上屏假名）
            if code == VK_SPACE:
                self._commit_candidate(self._current_global_index())
                return True
            # 上屏原始假名（方向键动过光标时，Enter 确认选中的候选）
            if cfg.match(keyEvent, 'commit_kana'):
                if self.showCandidates and self.candidateCursor > 0:
                    self._commit_candidate(self._current_global_index())
                else:
                    self._commit(self._display_kana())
                return True
            # 全部取消
            if cfg.match(keyEvent, 'cancel'):
                self._clear()
                return True
            # Backspace：回删一个罗马字字母
            if code == VK_BACK:
                self.romaji.backspace()
                self._refresh()
                return True
            # 候选窗内光标移动
            if self.showCandidates and cfg.match(keyEvent, 'cursor_up'):
                pos = (self.candidateCursor - 1) % len(self.candidateList)
                self.setCandidateCursor(pos)
                return True
            if self.showCandidates and cfg.match(keyEvent, 'cursor_down'):
                pos = (self.candidateCursor + 1) % len(self.candidateList)
                self.setCandidateCursor(pos)
                return True
            # 翻页：多页时翻页；单页时标点键（, .）仍可当标点，
            # 其它翻页绑定键（如 - =）直接吞掉，绝不落入罗马字转换
            c = chr(ch) if ch else ''
            if self.showCandidates and self._all_cands:
                pages = (len(self._all_cands) + _PAGE_SIZE - 1) // _PAGE_SIZE
                if cfg.match(keyEvent, 'page_up'):
                    if pages > 1:
                        self._turn_page(-1)
                        return True
                    if c not in _PUNCT_MAP:
                        return True
                if cfg.match(keyEvent, 'page_down'):
                    if pages > 1:
                        self._turn_page(1)
                        return True
                    if c not in _PUNCT_MAP:
                        return True
            # 标点：上屏首选候选并附日文标点（也记入学习）
            if c in _PUNCT_MAP:
                cand = (self.candidateList[self.candidateCursor]
                        if self.showCandidates and self.candidateList
                        else self._display_kana())
                self.history.record(kana_for_conversion(self._buffer()), cand)
                self._commit(cand + _PUNCT_MAP[c])
                return True
            # 小写字母 / 长音号 / 拨音撇号：继续输入
            if ord('a') <= ch <= ord('z') or c in ("'", '-'):
                self.romaji.input(c)
                self._refresh()
                return True
            # 其它可打印字符（数字无候选、符号等）：上屏当前内容后放行
            if keyEvent.isPrintableChar():
                self._commit(self._display_kana())
                return False
            return True

        # 空闲状态：小写字母开始组字；日文标点直接上屏
        if ord('a') <= ch <= ord('z'):
            self.romaji.input(chr(ch))
            self._refresh()
            return True
        c = chr(ch) if ch else ''
        if self.config.japanese_punct and c in _PUNCT_MAP:
            self.setCommitString(_PUNCT_MAP[c])
        return True

    def onCompositionTerminated(self, forced):
        TextService.onCompositionTerminated(self, forced)
        self.romaji.clear()
