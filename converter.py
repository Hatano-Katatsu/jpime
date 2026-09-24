# -*- coding: utf-8 -*-
"""假名 -> 汉字 转换引擎。

两种用法：
- KanaKanjiConverter: 直接在本进程跑 MeCab（需要 mozcpy + mecab-python3）
- ConverterProxy:     通过 stdin/stdout JSON 协议调用外部 helper 进程，
                      供 PIME 自带的 32 位 Python 3.8（装不了 MeCab 轮子）使用

引擎不可用时退化为只返回假名/片假名候选。
"""
import bisect
import json
import os
import pickle
import subprocess
import threading

from romaji import hira_to_kata, kana_for_conversion

_N_BEST = 20  # 向 MeCab 请求的候选数（去重后一般剩几个到十几个）
_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'predict_index.pkl')


class Predictor:
    """前缀联想：读音以 prefix 开头的词，按词频排序。"""

    def __init__(self, path=_INDEX_PATH):
        self._readings = None
        self._by_reading = None
        self._lock = threading.Lock()
        self._path = path

    def _load(self):
        with self._lock:
            if self._readings is not None:
                return True
            try:
                with open(self._path, 'rb') as fp:
                    self._readings, self._by_reading = pickle.load(fp)
                return True
            except Exception:  # noqa: BLE001
                self._readings = []
                self._by_reading = {}
                return False

    def query(self, prefix, limit=50):
        """返回读音以 prefix 开头（但不等于 prefix）的候选词，词频高的在前。"""
        if not prefix or not self._load() or not self._readings:
            return []
        lo = bisect.bisect_left(self._readings, prefix)
        hits = []
        readings = self._readings
        n = len(readings)
        i = lo
        while i < n and readings[i].startswith(prefix):
            hits.extend(self._by_reading[readings[i]])
            i += 1
        hits.sort(key=lambda wc: wc[1])
        seen = set()
        out = []
        for word, _ in hits:
            if word not in seen:
                seen.add(word)
                out.append(word)
                if len(out) >= limit:
                    break
        return out


def assemble_candidates(kana, exact, predict, limit=9):
    """拼装最终候选：精确转换在前，联想在后，末尾保底片假名/假名。"""
    seen = set()
    out = []

    def push(items, cap):
        for w in items:
            if len(out) >= cap:
                return
            if w and w not in seen:
                seen.add(w)
                out.append(w)

    push(exact, min(5, max(0, limit - 2)))   # 精确转换最多占 5 个位置
    push(predict, max(0, limit - 2))          # 联想填满剩余位置
    for fallback in (hira_to_kata(kana), kana):
        if fallback not in seen:
            out.append(fallback)
    return out[:limit]


class KanaKanjiConverter:
    """直接调用本进程的 MeCab（mozcpy 词典）+ 前缀联想索引。"""

    def __init__(self):
        self._tagger = None
        self._lock = threading.Lock()
        self._init_error = None
        self._predictor = Predictor()

    def _get_tagger(self):
        if self._tagger is None and self._init_error is None:
            try:
                import MeCab
                import mozcpy
                dic = os.path.join(os.path.dirname(mozcpy.__file__), 'dic')
                if ' ' in dic:
                    # MeCab 参数按空格分词，带空格的路径要换成 8.3 短路径
                    import ctypes
                    buf = ctypes.create_unicode_buffer(260)
                    ctypes.windll.kernel32.GetShortPathNameW(dic, buf, 260)
                    if buf.value and ' ' not in buf.value:
                        dic = buf.value
                args = '-d %s -r nul' % dic.replace('\\', '\\\\')
                tagger = MeCab.Tagger(args)
                tagger.parse('')  # 规避 MeCab 已知 bug
                self._tagger = tagger
            except Exception as e:  # noqa: BLE001
                self._init_error = e
        return self._tagger

    def convert_nbest(self, kana):
        """对假名串做 N-best 转换，返回原始候选列表。"""
        tagger = self._get_tagger()
        if tagger is None:
            return []
        with self._lock:
            raw = tagger.parseNBest(_N_BEST, kana)
        return raw.replace(' \n', '\n').splitlines() if raw else []

    def predict(self, kana, limit=50):
        return self._predictor.query(kana, limit)

    def candidates(self, romaji_buffer, limit=9):
        """输入罗马字缓冲（如 'kyouha'），返回候选列表（最多 limit 个）。"""
        kana = kana_for_conversion(romaji_buffer)
        if not kana:
            return []
        return assemble_candidates(kana, self.convert_nbest(kana),
                                   self.predict(kana), limit)

    @property
    def available(self):
        return self._get_tagger() is not None


class ConverterProxy:
    """通过子进程使用转换引擎（helper 里跑 KanaKanjiConverter）。

    config: {'python': python解释器路径, 'server': converter_server.py 路径}
    helper 崩溃后下次调用自动重启；彻底不可用时返回保底候选。
    """

    def __init__(self, config):
        self._python = config['python']
        self._server = config['server']
        self._proc = None
        self._lock = threading.Lock()

    def _ensure_proc(self):
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._proc = subprocess.Popen(
            [self._python, self._server],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(self._server),
            encoding='utf-8', errors='replace',
        )
        return self._proc

    def _query(self, kana):
        """返回 (精确转换列表, 联想列表)。"""
        with self._lock:
            try:
                proc = self._ensure_proc()
                req = json.dumps({'kana': kana}, ensure_ascii=False)
                proc.stdin.write(req + '\n')
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    raise IOError('helper closed')
                resp = json.loads(line)
                return resp.get('results', []), resp.get('predict', [])
            except Exception:  # noqa: BLE001
                try:
                    if self._proc:
                        self._proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                self._proc = None
                return [], []

    def convert_nbest(self, kana):
        return self._query(kana)[0]

    def candidates(self, romaji_buffer, limit=9):
        kana = kana_for_conversion(romaji_buffer)
        if not kana:
            return []
        exact, predict = self._query(kana)
        return assemble_candidates(kana, exact, predict, limit)


def create_converter(config_path=None):
    """优先本进程直转（有 MeCab 时），否则用 engine.json 配的 helper 进程。"""
    direct = KanaKanjiConverter()
    if direct.available:
        return direct
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'engine.json')
    try:
        with open(config_path, encoding='utf-8') as fp:
            config = json.load(fp)
        return ConverterProxy(config)
    except Exception:  # noqa: BLE001
        pass
    return direct  # 保底：引擎不可用也能出假名候选
