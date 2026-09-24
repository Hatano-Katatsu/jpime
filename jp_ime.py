#! python3
# -*- coding: utf-8 -*-
"""中文式交互的日语输入法 — PIME 模块。

交互设计（对齐中文拼音输入法习惯）：
- 输入罗马字立即显示假名 + 候选词窗口
- 数字键 1-9 直接选词上屏
- 空格上屏当前高亮候选（默认第一个）
- Enter 上屏原始假名，Esc 清空，Backspace 回删
- 中文标点映射：, -> 、  . -> 。  [ -> 「  ] -> 」  / -> ・
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

_SEL_KEYS = "123456789"
_PAGE_SIZE = 9          # 每页候选数
_MAX_PAGES = 5          # 最多 5 页（<> 翻页）

_PUNCT_MAP = {
    ',': '、',
    '.': '。',
    '[': '「',
    ']': '」',
    '/': '・',
}


class JpTextService(TextService):
    def __init__(self, client):
        TextService.__init__(self, client)
        self.icon_dir = os.path.abspath(os.path.dirname(__file__))
        self.romaji = RomajiConverter()
        self.converter = create_converter()
        self.history = UserHistory()
        self.english_mode = False   # Shift 单击切换 日文/纯英文
        self._shift_alone = False   # Shift 按下后是否还没碰过其它键
        self._all_cands = []        # 全部候选（分页前）
        self._page = 0

    def onActivate(self):
        TextService.onActivate(self)
        # 对齐微软拼音横排：一排 9 个候选、12pt、Yu Gothic UI
        self.customizeUI(candFontName='Yu Gothic UI',
                         candFontSize=12,
                         candPerRow=9,
                         candUseCursor=True)
        self.setSelKeys(_SEL_KEYS)
        self._buttons_added = set()

    def _apply_mode_icon(self):
        # 只在英文模式下显示 A 图标，避免和 Windows 自带的输入法图标重复
        if self.english_mode and 'windows-mode-icon' not in self._buttons_added:
            self.addButton('windows-mode-icon',
                           icon=os.path.join(self.icon_dir, 'icon_en.ico'),
                           tooltip='英文模式（单击 Shift 切回日文）')
            self._buttons_added.add('windows-mode-icon')
        elif not self.english_mode and 'windows-mode-icon' in self._buttons_added:
            self.removeButton('windows-mode-icon')
            self._buttons_added.discard('windows-mode-icon')

    def _set_english_mode(self, english):
        self.english_mode = english
        self._apply_mode_icon()

    def onDeactivate(self):
        if 'windows-mode-icon' in getattr(self, '_buttons_added', ()):
            self.removeButton('windows-mode-icon')
            self._buttons_added.discard('windows-mode-icon')
        TextService.onDeactivate(self)

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

    def filterKeyDown(self, keyEvent):
        # Shift 键本身要拦（单击切换 日文/英文 模式）
        if keyEvent.keyCode == VK_SHIFT:
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
        # 空闲时只拦小写字母（开始新的组字）
        return ord('a') <= keyEvent.charCode <= ord('z')

    def filterKeyUp(self, keyEvent):
        return keyEvent.keyCode == VK_SHIFT

    def onKeyUp(self, keyEvent):
        # Shift 单独点击（中间没碰其它键）-> 切换 日文/英文 模式
        if keyEvent.keyCode == VK_SHIFT and self._shift_alone:
            self._shift_alone = False
            if self.romaji:
                self._commit(self._display_kana())
            self._set_english_mode(not self.english_mode)
            return True
        return False

    def onKeyDown(self, keyEvent):
        ch = keyEvent.charCode
        code = keyEvent.keyCode

        if code == VK_SHIFT:
            return True  # 已在 filterKeyDown 里标记，抬起时才切换

        if self.english_mode:
            return False

        if self.romaji:
            # Tab：全角片假名上屏；`~ 键（Tab 左边）：半角片假名上屏
            if code == VK_TAB:
                self._commit(hira_to_kata(self._display_kana()))
                return True
            if code == VK_OEM_3:
                self._commit(hira_to_half_kata(self._display_kana()))
                return True
            # 数字键选词（选当前页的第 N 个）
            if ord('1') <= ch <= ord('9') and self.showCandidates:
                self._commit_candidate(self._page * _PAGE_SIZE + ch - ord('1'))
                return True
            # 空格：上屏高亮候选（无候选则上屏假名）
            if code == VK_SPACE:
                self._commit_candidate(self._current_global_index())
                return True
            # Enter：上屏原始假名
            if code == VK_RETURN:
                self._commit(self._display_kana())
                return True
            # Esc：全部取消
            if code == VK_ESCAPE:
                self._clear()
                return True
            # Backspace：回删一个罗马字字母
            if code == VK_BACK:
                self.romaji.backspace()
                self._refresh()
                return True
            # 候选窗内光标移动
            if self.showCandidates and code in (VK_UP, VK_DOWN):
                delta = -1 if code == VK_UP else 1
                pos = (self.candidateCursor + delta) % len(self.candidateList)
                self.setCandidateCursor(pos)
                return True
            # , . / <> / PageUp / PageDown 翻页（有多页时优先翻页，否则逗号句号当标点）
            c = chr(ch) if ch else ''
            if self.showCandidates and self._all_cands:
                pages = (len(self._all_cands) + _PAGE_SIZE - 1) // _PAGE_SIZE
                if pages > 1 and (c in ',.<>' or code in (VK_PRIOR, VK_NEXT)):
                    self._turn_page(1 if c in '.>' or code == VK_NEXT else -1)
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

        # 空闲状态：小写字母开始组字
        if ord('a') <= ch <= ord('z'):
            self.romaji.input(chr(ch))
            self._refresh()
        return True

    def onCompositionTerminated(self, forced):
        TextService.onCompositionTerminated(self, forced)
        self.romaji.clear()
