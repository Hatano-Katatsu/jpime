# -*- coding: utf-8 -*-
import os
import sys
import time

import pytest

from converter import ConverterProxy, KanaKanjiConverter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def conv():
    return KanaKanjiConverter()


class TestEngine:
    def test_available(self, conv):
        assert conv.available, conv._init_error

    def test_basic_word(self, conv):
        cands = conv.candidates('kyou')
        assert cands[0] == '今日'

    def test_sentence(self, conv):
        cands = conv.candidates('watashihagakuseidesu')
        assert '私は学生です' in cands

    def test_fallback_kana_and_katakana(self, conv):
        cands = conv.candidates('hogehoge')
        assert 'ホゲホゲ' in cands
        assert 'ほげほげ' in cands

    def test_trailing_pending_n(self, conv):
        # 尾部挂起的 n 按 ん 转换
        cands = conv.candidates('kan')
        assert any('ん' in c or '間' in c or '感' in c or '漢' in c for c in cands)

    def test_pending_tail_stripped(self, conv):
        cands = conv.candidates('kyouk')
        assert cands
        assert all('k' not in c for c in cands)

    def test_empty(self, conv):
        assert conv.candidates('') == []
        assert conv.candidates('ky') == []

    def test_limit(self, conv):
        assert len(conv.candidates('kyou', limit=5)) <= 5

    def test_latency(self, conv):
        conv.candidates('kyou')  # 预热
        t0 = time.perf_counter()
        for _ in range(20):
            conv.candidates('kyouhahaadesu')
        avg = (time.perf_counter() - t0) / 20
        assert avg < 0.05, f'转换太慢: {avg*1000:.1f}ms/次'


@pytest.fixture(scope='module')
def proxy():
    return ConverterProxy({
        'python': sys.executable,
        'server': os.path.join(HERE, 'converter_server.py'),
    })


class TestProxy:
    """helper 进程模式（PIME 自带的 Python 3.8 走这条路）。"""

    def test_basic(self, proxy):
        cands = proxy.candidates('kyou')
        assert cands[0] == '今日'

    def test_fallback_present(self, proxy):
        cands = proxy.candidates('hogehoge')
        assert 'ホゲホゲ' in cands
        assert 'ほげほげ' in cands

    def test_survives_helper_crash(self, proxy):
        proxy.candidates('kyou')
        proxy._proc.kill()  # 模拟 helper 崩溃
        proxy._proc.wait()
        cands = proxy.candidates('watashi')
        assert cands[0] == '私'

    def test_empty(self, proxy):
        assert proxy.candidates('') == []
