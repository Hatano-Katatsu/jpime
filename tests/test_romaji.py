# -*- coding: utf-8 -*-
import pytest

from romaji import RomajiConverter, kana_for_conversion, to_kana


def type_str(conv, s):
    for ch in s:
        conv.input(ch)
    return conv.display()


class TestBasic:
    def test_single_vowels(self):
        assert to_kana('aiueo') == 'あいうえお'

    def test_basic_syllables(self):
        assert to_kana('kanji') == 'かんじ'
        assert to_kana('nihongo') == 'にほんご'
        assert to_kana('kyou') == 'きょう'

    def test_alternative_spellings(self):
        assert to_kana('shi') == 'し'
        assert to_kana('si') == 'し'
        assert to_kana('chi') == 'ち'
        assert to_kana('ti') == 'ち'
        assert to_kana('tsu') == 'つ'
        assert to_kana('tu') == 'つ'
        assert to_kana('fu') == 'ふ'
        assert to_kana('hu') == 'ふ'
        assert to_kana('ji') == 'じ'
        assert to_kana('zi') == 'じ'

    def test_youon(self):
        assert to_kana('kyouha') == 'きょうは'
        assert to_kana('shashin') == 'しゃしn'  # 尾部 n 挂起
        assert to_kana('chuugoku') == 'ちゅうごく'
        assert to_kana('ryokou') == 'りょこう'


class TestN:
    def test_nn(self):
        assert to_kana('konnichiha') == 'こんにちは'
        assert to_kana('konnitiha') == 'こんにちは'  # n+n+元音 -> ん+な行
        assert to_kana('kanngaeru') == 'かんがえる'  # nn+辅音 -> ん

    def test_n_before_consonant(self):
        assert to_kana('kanji') == 'かんじ'
        assert to_kana('senpai') == 'せんぱい'

    def test_n_before_vowel_pending(self):
        # n 后面可能是 な行，挂起显示
        assert to_kana('kan') == 'かn'
        assert to_kana('kani') == 'かに'

    def test_n_before_y_pending(self):
        assert to_kana('konya') == 'こにゃ'

    def test_n_apostrophe(self):
        assert to_kana("kin'i") == 'きんい'
        assert to_kana("kan'atsu") == 'かんあつ'

    def test_n_end_pending(self):
        assert to_kana('kon') == 'こn'


class TestSokuon:
    def test_double_consonant(self):
        assert to_kana('zutto') == 'ずっと'
        assert to_kana('kitte') == 'きって'
        assert to_kana('gakkou') == 'がっこう'

    def test_tch(self):
        assert to_kana('matcha') == 'まっちゃ'

    def test_pending_double(self):
        assert to_kana('zutt') == 'ずっt'


class TestSpecial:
    def test_long_vowel(self):
        assert to_kana('ko-hi-') == 'こーひー'

    def test_small_kana(self):
        assert to_kana('xya') == 'ゃ'
        assert to_kana('ltu') == 'っ'

    def test_foreign_sounds(self):
        assert to_kana('famiri-') == 'ふぁみりー'
        assert to_kana('vaza') == 'ゔぁざ'

    def test_pending_consonant(self):
        assert to_kana('ky') == 'ky'
        assert to_kana('kak') == 'かk'

    def test_passthrough(self):
        assert to_kana('a1') == 'あ1'


class TestEditing:
    def test_backspace(self):
        conv = RomajiConverter()
        type_str(conv, 'kanji')
        conv.backspace()  # 'i'
        assert conv.display() == 'かんj'
        conv.backspace()  # 'j'
        assert conv.display() == 'かn'  # 尾部 n 挂起，转换时视为 ん
        conv.backspace()  # 'n'
        assert conv.display() == 'か'

    def test_kana_for_conversion(self):
        assert kana_for_conversion('kan') == 'かん'
        assert kana_for_conversion('kyouk') == 'きょう'
        assert kana_for_conversion('kyou') == 'きょう'
        assert kana_for_conversion('ky') == ''
        assert kana_for_conversion('n') == 'ん'

    def test_clear(self):
        conv = RomajiConverter()
        type_str(conv, 'abc')
        assert conv.clear() == ''
        assert not conv

    def test_bool(self):
        conv = RomajiConverter()
        assert not conv
        conv.input('a')
        assert conv
