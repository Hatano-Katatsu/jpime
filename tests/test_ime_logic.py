# -*- coding: utf-8 -*-
"""不依赖 Windows 的端到端逻辑测试：
把 PIME 的 textService.py / keycodes.py 加入路径，直接驱动 JpTextService。
"""
import os
import sys

import pytest

PIME_PY = r'C:\Program Files (x86)\PIME\python'
if not os.path.isdir(PIME_PY):
    pytest.skip('PIME 未安装', allow_module_level=True)

sys.path.insert(0, PIME_PY)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jp_ime import JpTextService  # noqa: E402

VK_BACK = 0x08
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_UP = 0x26
VK_DOWN = 0x28
VK_OEM_COMMA = 0xBC
VK_OEM_PERIOD = 0xBE


def make_msg(method, char=None, vk=None, caps=False):
    keyStates = [0] * 256
    if caps:
        keyStates[0x14] = 1  # VK_CAPITAL toggled
    return {
        'method': method,
        'seqNum': 1,
        'charCode': ord(char) if char else 0,
        'keyCode': vk if vk is not None else (ord(char.upper()) if char else 0),
        'repeatCount': 1,
        'scanCode': 0,
        'isExtended': False,
        'keyStates': keyStates,
    }


@pytest.fixture()
def svc(tmp_path):
    from config import Config
    from user_history import UserHistory
    s = JpTextService(client=None)
    s.history = UserHistory(path=str(tmp_path / 'history.json'))  # 隔离的用户历史
    s.config = Config(path=str(tmp_path / 'config.json'))         # 隔离的配置
    s.onActivate()
    return s


def type_text(svc, text):
    for ch in text:
        msg = make_msg('filterKeyDown', char=ch)
        assert svc.handleRequest(msg)['return'] is True
        svc.handleRequest(make_msg('onKeyDown', char=ch))


def press(svc, vk):
    svc.handleRequest(make_msg('filterKeyDown', vk=vk))
    return svc.handleRequest(make_msg('onKeyDown', vk=vk))


class TestFlow:
    def test_type_and_select_first(self, svc):
        type_text(svc, 'kyou')
        assert svc.compositionString == 'きょう'
        assert svc.showCandidates
        assert svc.candidateList[0] == '今日'
        type_text(svc, '1')
        assert svc.commitString == '今日'
        assert svc.compositionString == ''
        assert not svc.showCandidates

    def test_space_commits_highlighted(self, svc):
        type_text(svc, 'watashi')
        assert '私' in svc.candidateList
        first = svc.candidateList[0]
        press(svc, VK_SPACE)
        assert svc.commitString == first

    def test_enter_commits_kana(self, svc):
        type_text(svc, 'kyou')
        press(svc, VK_RETURN)
        assert svc.commitString == 'きょう'

    def test_escape_cancels(self, svc):
        type_text(svc, 'kyou')
        press(svc, VK_ESCAPE)
        assert svc.compositionString == ''
        assert svc.commitString == ''
        assert not svc.showCandidates

    def test_backspace_refreshes(self, svc):
        type_text(svc, 'kyous')
        assert svc.compositionString == 'きょうs'
        press(svc, VK_BACK)
        assert svc.compositionString == 'きょう'
        assert svc.candidateList[0] == '今日'

    def test_cursor_navigation(self, svc):
        type_text(svc, 'kyou')
        assert svc.candidateCursor == 0
        press(svc, VK_DOWN)
        assert svc.candidateCursor == 1
        second = svc.candidateList[1]
        press(svc, VK_SPACE)
        assert svc.commitString == second

    def test_punctuation_commits_and_appends(self, svc):
        svc.converter = _StubConverter(['今日', 'きょう'])  # 不足一页时标点仍是标点
        type_text(svc, 'kyou')
        type_text(svc, '.')
        assert svc.commitString.endswith('。')

    def test_idle_passthrough(self, svc):
        # 空闲时数字键不拦截
        msg = make_msg('filterKeyDown', char='5')
        assert svc.handleRequest(msg)['return'] is False

    def test_continue_typing_with_candidates_open(self, svc):
        type_text(svc, 'kyou')
        assert svc.showCandidates
        type_text(svc, 'ha')
        assert svc.compositionString == 'きょうは'
        assert any('今日は' in c for c in svc.candidateList)


class TestLearning:
    def test_selection_boosts_next_time(self, svc, tmp_path):
        from user_history import UserHistory
        svc.history = UserHistory(path=str(tmp_path / 'h.json'))
        type_text(svc, 'kyou')
        # 选一个非首选候选（比如 強）
        target = next(c for c in svc.candidateList if c not in ('今日', 'きょう'))
        idx = svc.candidateList.index(target)
        type_text(svc, str(idx + 1))
        assert svc.commitString == target
        # 再次输入同样的读音，学过的词应排在最前
        type_text(svc, 'kyou')
        assert svc.candidateList[0] == target

    def test_raw_kana_commit_not_recorded(self, svc, tmp_path):
        from user_history import UserHistory
        svc.history = UserHistory(path=str(tmp_path / 'h.json'))
        type_text(svc, 'kyou')
        press(svc, VK_RETURN)  # 上屏假名不算选词
        assert svc.history._data == {}


class _StubConverter:
    def __init__(self, cands):
        self._cands = cands

    def candidates(self, buf, limit=9):
        return self._cands[:limit]


class TestPaging:
    @pytest.fixture()
    def paged_svc(self, svc):
        svc.converter = _StubConverter([f'词{i}' for i in range(1, 26)])  # 25 个候选
        return svc

    def press_char(self, svc, char, vk):
        svc.handleRequest(make_msg('filterKeyDown', char=char, vk=vk))
        svc.handleRequest(make_msg('onKeyDown', char=char, vk=vk))

    def test_page_down_and_select(self, paged_svc):
        type_text(paged_svc, 'a')
        assert paged_svc.candidateList[0] == '词1'
        assert len(paged_svc.candidateList) == 9
        self.press_char(paged_svc, '>', vk=VK_OEM_PERIOD)
        assert paged_svc.candidateList[0] == '词10'
        type_text(paged_svc, '1')  # 选第 2 页第 1 个
        assert paged_svc.commitString == '词10'

    def test_page_wrap_around(self, paged_svc):
        type_text(paged_svc, 'a')
        self.press_char(paged_svc, '<', vk=VK_OEM_COMMA)  # 第 1 页再上一页 -> 最后一页
        assert paged_svc.candidateList[0] == '词19'

    def test_page_resets_on_new_input(self, paged_svc):
        type_text(paged_svc, 'a')
        self.press_char(paged_svc, '>', vk=VK_OEM_PERIOD)
        type_text(paged_svc, 'i')
        assert paged_svc.candidateList[0] == '词1'

    def test_space_uses_page_cursor(self, paged_svc):
        type_text(paged_svc, 'a')
        self.press_char(paged_svc, '>', vk=VK_OEM_PERIOD)
        press(paged_svc, VK_DOWN)
        press(paged_svc, VK_SPACE)
        assert paged_svc.commitString == '词11'

    def test_comma_pages_when_multi_page(self, paged_svc):
        type_text(paged_svc, 'a')
        self.press_char(paged_svc, '.', vk=VK_OEM_PERIOD)  # 未按 Shift 的 . 也翻页
        assert paged_svc.candidateList[0] == '词10'
        self.press_char(paged_svc, ',', vk=VK_OEM_COMMA)
        assert paged_svc.candidateList[0] == '词1'

    def test_comma_is_punct_when_single_page(self, svc):
        svc.converter = _StubConverter(['今日', 'きょう'])
        type_text(svc, 'kyou')
        type_text(svc, ',')
        assert svc.commitString.endswith('、')


VK_TAB = 0x09
VK_SHIFT = 0x10
VK_OEM_3 = 0xC0


class TestKanaConvert:
    def press_key(self, svc, vk, char=None):
        svc.handleRequest(make_msg('filterKeyDown', vk=vk, char=char))
        return svc.handleRequest(make_msg('onKeyDown', vk=vk, char=char))

    def test_tab_full_katakana(self, svc):
        type_text(svc, 'ko-hi-')
        self.press_key(svc, VK_TAB)
        assert svc.commitString == 'コーヒー'

    def test_backquote_half_katakana(self, svc):
        type_text(svc, 'ko-hi-')
        self.press_key(svc, VK_OEM_3, '`')
        assert svc.commitString == 'ｺｰﾋｰ'

    def test_backquote_voiced(self, svc):
        type_text(svc, 'gakkou')
        self.press_key(svc, VK_OEM_3, '`')
        assert svc.commitString == 'ｶﾞｯｺｳ'

    def test_enter_still_hiragana(self, svc):
        type_text(svc, 'ko-hi-')
        press(svc, VK_RETURN)
        assert svc.commitString == 'こーひー'


class TestEnglishMode:
    def shift_tap(self, svc):
        press(svc, VK_SHIFT)  # keydown
        svc.handleRequest(make_msg('filterKeyUp', vk=VK_SHIFT))
        svc.handleRequest(make_msg('onKeyUp', vk=VK_SHIFT))

    def test_shift_toggles_english(self, svc):
        assert not svc.english_mode
        self.shift_tap(svc)
        assert svc.english_mode
        # 英文模式下字母不拦截
        msg = make_msg('filterKeyDown', char='k')
        assert svc.handleRequest(msg)['return'] is False
        self.shift_tap(svc)
        assert not svc.english_mode
        msg = make_msg('filterKeyDown', char='k')
        assert svc.handleRequest(msg)['return'] is True

    def test_shift_with_other_key_does_not_toggle(self, svc):
        # Shift+A（大写输入）不应触发模式切换
        press(svc, VK_SHIFT)          # shift down，标记 alone
        msg = make_msg('filterKeyDown', char='A')
        svc.handleRequest(msg)        # 其它键按下，清除 alone 标记
        svc.handleRequest(make_msg('filterKeyUp', vk=VK_SHIFT))
        svc.handleRequest(make_msg('onKeyUp', vk=VK_SHIFT))
        assert not svc.english_mode

    def test_shift_tap_commits_pending_kana(self, svc):
        type_text(svc, 'kyou')
        self.shift_tap(svc)
        assert svc.english_mode
        assert svc.commitString == 'きょう'
        assert svc.compositionString == ''


class TestCustomKeymap:
    def test_custom_full_kata_key(self, svc, tmp_path):
        # 把全角片假名从 Tab 改绑到 F8
        cfg = tmp_path / 'config.json'
        cfg.write_text('{"keymap": {"commit_full_katakana": ["f8"]}}',
                       encoding='utf-8')
        from config import Config
        svc.config = Config(path=str(cfg))
        type_text(svc, 'kawa')
        press(svc, 0x77)  # VK_F8
        assert svc.commitString == 'カワ'

    def test_default_still_works(self, svc):
        type_text(svc, 'kawa')
        press(svc, VK_TAB)
        assert svc.commitString == 'カワ'


class TestModeSwitchMessage:
    def shift_tap(self, svc):
        press(svc, VK_SHIFT)  # keydown
        svc.handleRequest(make_msg('filterKeyUp', vk=VK_SHIFT))
        return svc.handleRequest(make_msg('onKeyUp', vk=VK_SHIFT))

    def test_shows_message_on_toggle(self, svc):
        reply = self.shift_tap(svc)
        assert svc.english_mode
        assert reply['showMessage'] == {'message': '英文模式', 'duration': 2}
        reply = self.shift_tap(svc)
        assert not svc.english_mode
        assert reply['showMessage'] == {'message': '日文模式', 'duration': 2}

    def test_no_buttons_registered(self, svc):
        # 托盘图标由独立程序提供，PIME 不再注册语言栏按钮
        assert not getattr(svc, '_buttons_added', set())


class TestJapanesePunct:
    def idle_type(self, svc, char):
        msg = make_msg('filterKeyDown', char=char)
        intercepted = svc.handleRequest(msg)['return']
        if intercepted:
            svc.handleRequest(make_msg('onKeyDown', char=char))
        return intercepted

    def test_idle_comma_commits_touten(self, svc):
        assert self.idle_type(svc, ',') is True
        assert svc.commitString == '、'
        assert svc.compositionString == ''  # 不进入组字

    def test_idle_question_commits_fullwidth(self, svc):
        assert self.idle_type(svc, '?') is True
        assert svc.commitString == '？'

    def test_idle_various_puncts(self, svc):
        for src, dst in [('[', '「'), (']', '」'), ('/', '・'), ('!', '！'),
                         ('(', '（'), (')', '）'), (':', '：'), (';', '；'),
                         ('~', '〜'), ('\\', '¥'), ('@', '＠')]:
            svc.commitString = ''
            assert self.idle_type(svc, src) is True, src
            assert svc.commitString == dst, src

    def test_composing_punct_commits_candidate_plus_punct(self, svc):
        svc.converter = _StubConverter(['今日', 'きょう'])  # 不足一页，! 不作翻页键
        type_text(svc, 'kyou')
        type_text(svc, '!')
        assert svc.commitString == '今日！'

    def test_disabled_idle_passthrough(self, svc, tmp_path):
        cfg = tmp_path / 'config.json'
        cfg.write_text('{"japanese_punct": false}', encoding='utf-8')
        from config import Config
        svc.config = Config(path=str(cfg))
        assert svc.config.japanese_punct is False
        # 空闲按 , 原样透传：filterKeyDown 返回 False
        assert self.idle_type(svc, ',') is False
        assert svc.commitString == ''

    def test_full_map_via_config_default(self, svc):
        # 默认开启
        assert svc.config.japanese_punct is True


class TestEnterAfterCursorMove:
    def test_enter_commits_selected_after_move(self, svc):
        type_text(svc, 'kyou')
        press(svc, VK_DOWN)
        selected = svc.candidateList[1]
        press(svc, VK_RETURN)
        assert svc.commitString == selected

    def test_enter_kana_when_cursor_untouched(self, svc):
        type_text(svc, 'kyou')
        press(svc, VK_RETURN)
        assert svc.commitString == 'きょう'


class TestSelectionKeyPurity:
    def test_out_of_range_digit_is_swallowed(self, svc):
        svc.converter = _StubConverter(['今日', 'きょう', '強'])
        type_text(svc, 'kyou')
        type_text(svc, '9')  # 只有 3 个候选，按 9 不应有任何效果
        assert svc.commitString == ''
        assert svc.compositionString == 'きょう'
        assert svc.showCandidates  # 候选窗还在

    def test_valid_digit_still_selects(self, svc):
        svc.converter = _StubConverter(['今日', 'きょう', '強'])
        type_text(svc, 'kyou')
        type_text(svc, '3')
        assert svc.commitString == '強'


class TestDashEqualPaging:
    def test_combined_token_is_split(self, svc, tmp_path):
        # 用户写 "-="（粘连写法）也应识别为两个键
        cfg_file = tmp_path / 'config.json'
        cfg_file.write_text('{"keymap": {"page_down": ["-="]}}', encoding='utf-8')
        from config import Config
        svc.config = Config(path=str(cfg_file))
        svc.converter = _StubConverter([f'词{i}' for i in range(1, 29)])
        type_text(svc, 'a')
        type_text(svc, '=')
        assert svc.candidateList[0] == '词10'  # = 翻到第 2 页
        type_text(svc, '-')
        assert svc.candidateList[0] == '词19'  # - 也命中 page_down，翻到第 3 页

    def test_dash_swallowed_when_single_page(self, svc, tmp_path):
        # 单页候选时按 - 不做事，更不能变成促音长音 ー
        cfg_file = tmp_path / 'config.json'
        cfg_file.write_text('{"keymap": {"page_up": ["-"]}}', encoding='utf-8')
        from config import Config
        svc.config = Config(path=str(cfg_file))
        svc.converter = _StubConverter(['今日', 'きょう'])
        type_text(svc, 'kyou')
        type_text(svc, '-')
        assert svc.compositionString == 'きょう'  # 缓冲没变
        assert svc.commitString == ''


class TestArrowPaging:
    def test_left_right_paging(self, svc):
        svc.converter = _StubConverter([f'词{i}' for i in range(1, 26)])
        type_text(svc, 'a')
        press(svc, 0x27)  # VK_RIGHT 下一页
        assert svc.candidateList[0] == '词10'
        press(svc, 0x25)  # VK_LEFT 上一页
        assert svc.candidateList[0] == '词1'


class TestConverterSingleton:
    def test_instances_share_converter(self, svc):
        # 单例：多个输入法实例共享同一个转换引擎（同一 helper 进程）
        import jp_ime
        s2 = JpTextService(client=None)
        assert svc.converter is s2.converter
        assert svc.converter is jp_ime._get_converter()
