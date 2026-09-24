#! python3
# -*- coding: utf-8 -*-
"""转换引擎 helper 进程：stdin/stdout JSON 行协议。

请求:  {"kana": "きょうは"}
响应:  {"results": ["今日は", ...]}

由 ConverterProxy 按需启动；stdin 关闭时自动退出。
"""
import json
import os
import sys

# 便携运行时：脚本自身目录 + 解释器旁边的 site-packages
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_SP = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                   'site-packages')
if os.path.isdir(_SP) and _SP not in sys.path:
    sys.path.insert(0, _SP)

from converter import KanaKanjiConverter


def main():
    conv = KanaKanjiConverter()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            kana = req.get('kana', '')
            results = conv.convert_nbest(kana)
            pe, pp = conv.split_predict(kana)
        except Exception:  # noqa: BLE001
            results, pe, pp = [], [], []
        sys.stdout.write(json.dumps({'results': results, 'pe': pe, 'pp': pp},
                                    ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
