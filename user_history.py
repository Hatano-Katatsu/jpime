# -*- coding: utf-8 -*-
"""用户学习：记录用户选过的候选，下次优先排前面。

存储: %APPDATA%\\jpime\\user_history.json
结构: {读音假名: {候选词: 选择次数}}
"""
import json
import os
import threading

_MAX_WORDS_PER_READING = 20   # 每个读音最多记多少个候选
_MAX_READINGS = 50000         # 读音总数上限（防爆）

if 'APPDATA' in os.environ:
    _STORE_DIR = os.path.join(os.environ['APPDATA'], 'jpime')
else:  # 测试环境
    _STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.user_data')


class UserHistory:
    def __init__(self, path=None):
        self._path = path or os.path.join(_STORE_DIR, 'user_history.json')
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _load(self):
        try:
            with open(self._path, encoding='utf-8') as fp:
                self._data = json.load(fp)
        except Exception:  # noqa: BLE001
            self._data = {}

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fp:
            json.dump(self._data, fp, ensure_ascii=False)
        os.replace(tmp, self._path)

    def record(self, reading, word):
        """用户为读音 reading 选择了 word。"""
        if not reading or not word or reading == word:
            return
        with self._lock:
            words = self._data.setdefault(reading, {})
            words[word] = words.get(word, 0) + 1
            if len(words) > _MAX_WORDS_PER_READING:
                # 只保留次数最多的前 N 个
                top = sorted(words.items(), key=lambda kv: -kv[1])
                self._data[reading] = dict(top[:_MAX_WORDS_PER_READING])
            if len(self._data) > _MAX_READINGS:
                # 简单淘汰：砍掉一半最冷门的读音
                keys = sorted(self._data,
                              key=lambda k: -sum(self._data[k].values()))
                self._data = {k: self._data[k] for k in keys[:_MAX_READINGS // 2]}
            try:
                self._save()
            except Exception:  # noqa: BLE001
                pass

    def rerank(self, reading, candidates):
        """按学习记录重排候选：学过的词按选择次数提到前面。"""
        if not candidates or reading not in self._data:
            return candidates
        learned = self._data[reading]
        boosted = sorted(
            (c for c in candidates if c in learned),
            key=lambda c: -learned[c])
        rest = [c for c in candidates if c not in learned]
        return boosted + rest
