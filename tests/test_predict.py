# -*- coding: utf-8 -*-
"""前缀联想索引的构建与查询测试（用小词典，不等真实下载）。"""
import os

import pytest

from build_predict_index import build
from converter import Predictor, assemble_candidates


@pytest.fixture(scope='module')
def index(tmp_path_factory):
    d = tmp_path_factory.mktemp('dict')
    src = d / 'dictionary00.txt'
    src.write_text(
        'さく\t100\t100\t500\t咲く\n'
        'さく\t100\t100\t900\t裂く\n'
        'さくら\t100\t100\t300\t桜\n'
        'さくら\t100\t100\t800\t佐倉\n'
        'さく\t100\t100\t100\tさく\n'          # 纯假名应被过滤
        'さくせん\t100\t100\t200\t作戦\n'
        'きょう\t100\t100\t100\t今日\n',
        encoding='utf-8')
    out = d / 'predict_index.pkl'
    build([str(src)], str(out))
    return str(out)


class TestPredictor:
    def test_prefix(self, index):
        p = Predictor(index)
        # 按词频（成本升序）排序：作戦200 桜300 咲く500 佐倉800 裂く900
        assert p.query('さく') == ['作戦', '桜', '咲く', '佐倉', '裂く']

    def test_exact_included(self, index):
        p = Predictor(index)
        # 精确匹配的词也进联想（与精确转换去重由 assemble 负责）
        assert p.query('さくら') == ['桜', '佐倉']

    def test_no_match(self, index):
        p = Predictor(index)
        assert p.query('ぴよ') == []

    def test_missing_index_file(self, tmp_path):
        p = Predictor(str(tmp_path / 'nonexistent.pkl'))
        assert p.query('さく') == []


class TestAssemble:
    def test_order(self):
        out = assemble_candidates('きょう', ['今日', '京'], ['教師', '京大'], 9)
        assert out[0] == '今日'
        assert '教師' in out
        assert 'キョウ' in out and 'きょう' in out  # 保底候选仍在

    def test_exact_capped(self):
        exact = [f'词{i}' for i in range(10)]
        out = assemble_candidates('あ', exact, ['联想'], 9)
        assert out[:5] == exact[:5]  # 精确转换最多 5 个
        assert '联想' in out

    def test_no_predict(self):
        out = assemble_candidates('きょう', ['今日'], [], 9)
        assert out == ['今日', 'キョウ', 'きょう']
