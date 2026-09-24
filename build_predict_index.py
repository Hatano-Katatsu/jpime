#! python3
# -*- coding: utf-8 -*-
"""从 mozc dictionary_oss 文本构建前缀联想索引。

词典格式: 读音<TAB>左ID<TAB>右ID<TAB>成本<TAB>词   (成本越小越常用)
产物: predict_index.pkl -> (readings 有序数组, reading -> [(词, 成本)...] 字典)
用法: python build_predict_index.py dict_src/dictionary0*.txt
"""
import glob
import pickle
import sys


def build(patterns, out_path):
    by_reading = {}
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    assert files, '未找到词典文件'
    for path in files:
        with open(path, encoding='utf-8') as fp:
            for line in fp:
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 5:
                    continue
                reading, _, _, cost, word = parts[0], parts[1], parts[2], parts[3], parts[4]
                if word == reading:  # 纯假名词没有联想价值
                    continue
                try:
                    cost = int(cost)
                except ValueError:
                    continue
                by_reading.setdefault(reading, []).append((word, cost))
    # 每个读音内部按词频（成本升序）排序
    for reading in by_reading:
        by_reading[reading].sort(key=lambda wc: wc[1])
    readings = sorted(by_reading)
    with open(out_path, 'wb') as fp:
        pickle.dump((readings, by_reading), fp, protocol=4)
    print(f'{len(readings)} 个读音, 写入 {out_path}')


if __name__ == '__main__':
    build(sys.argv[1:] or ['dict_src/dictionary0*.txt'], 'predict_index.pkl')
