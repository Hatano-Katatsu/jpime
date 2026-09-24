# -*- coding: utf-8 -*-
"""真实协议级验证：用 PIME 自带的 32 位 Python 3.8 跑它的 server.py，
加载 jpime 模块，按 PIMELauncher 的 stdin/stdout 协议驱动一整轮输入。
不依赖管理员权限（整个 PIME python 目录复制到可写位置）。"""
import json
import os
import shutil
import subprocess
import sys

PIME_PY = r'C:\Program Files (x86)/PIME\python'
PIME_PY38 = os.path.join(PIME_PY, 'python3', 'python.exe')
HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.join(HERE, '.pime_test')
GUID = '{DA3AF487-B408-4C4F-B9BE-CD1D1243F703}'

VK_BACK, VK_RETURN, VK_ESCAPE, VK_SPACE, VK_DOWN = 0x08, 0x0D, 0x1B, 0x20, 0x28


def setup_sandbox():
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)
    # 复制 PIME 的 python 后端（含自带解释器）
    shutil.copytree(PIME_PY, os.path.join(SANDBOX, 'python'),
                    ignore=shutil.ignore_patterns('__pycache__'))
    # 放入最新模块
    mod_dir = os.path.join(SANDBOX, 'python', 'input_methods', 'jpime')
    os.makedirs(mod_dir, exist_ok=True)
    for f in ('ime.json', 'jp_ime.py', 'romaji.py', 'converter.py',
              'converter_server.py', 'user_history.py', 'icon.ico', 'icon_en.ico'):
        shutil.copy2(os.path.join(HERE, f), os.path.join(mod_dir, f))
    with open(os.path.join(mod_dir, 'engine.json'), 'w', encoding='utf-8') as fp:
        json.dump({'python': os.path.join(HERE, '.venv', 'Scripts', 'python.exe'),
                   'server': os.path.join(mod_dir, 'converter_server.py')}, fp)


class Server:
    def __init__(self):
        env = dict(os.environ, PYTHONIOENCODING='utf-8:ignore')
        self.proc = subprocess.Popen(
            [os.path.join(SANDBOX, 'python', 'python3', 'python.exe'),
             'server.py'],
            cwd=os.path.join(SANDBOX, 'python'),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env,
            encoding='utf-8')

    def request(self, msg, client='c1'):
        self.proc.stdin.write(client + '|' + json.dumps(msg) + '\n')
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                err = self.proc.stderr.read()
                raise RuntimeError('server died: ' + err)
            if line.startswith('PIME_MSG|'):
                return json.loads(line.split('|', 2)[2])
            print('[server]', line.rstrip())  # 调试输出

    def key(self, ch=None, vk=None):
        msg = {'method': 'filterKeyDown', 'seqNum': 1,
               'charCode': ord(ch) if ch else 0,
               'keyCode': vk if vk is not None else ord(ch.upper()),
               'repeatCount': 1, 'scanCode': 0, 'isExtended': False,
               'keyStates': [0] * 256}
        filtered = self.request(msg).get('return', False)
        if not filtered:
            return {}
        msg['method'] = 'onKeyDown'
        return self.request(msg)

    def type(self, text):
        reply = {}
        for ch in text:
            reply = self.key(ch)
        return reply

    def close(self):
        self.proc.kill()


def main():
    if not os.path.isfile(PIME_PY38):
        sys.exit('未找到 PIME 自带 Python: ' + PIME_PY38)
    print('使用解释器:', PIME_PY38)
    setup_sandbox()
    srv = Server()

    r = srv.request({'method': 'init', 'seqNum': 0, 'id': GUID,
                     'isWindows8Above': True, 'isMetroApp': False,
                     'isUiLess': False, 'isConsole': False})
    assert r.get('success'), r
    print('init ok')

    r = srv.request({'method': 'onActivate', 'seqNum': 1,
                     'isKeyboardOpen': True})
    assert r.get('success'), r

    r = srv.type('kyou')
    assert r.get('compositionString') == 'きょう', r
    cands = r.get('candidateList', [])
    print('候选:', cands[:5])
    assert cands and cands[0] == '今日', cands
    assert r.get('showCandidates') is True

    r = srv.key('1')
    assert r.get('commitString') == '今日', r
    print('数字键选词 ok: 今日')

    r = srv.type('watashihaneko')
    assert r.get('compositionString') == 'わたしはねこ', r
    print('整句候选:', r.get('candidateList', [])[:3])

    r = srv.key(vk=VK_RETURN)
    assert r.get('commitString') == 'わたしはねこ', r
    print('Enter 上屏假名 ok')

    r = srv.type('kan')
    r = srv.key(vk=VK_SPACE)
    assert 'ん' in r.get('commitString', '') or '間' in r.get('commitString', '') \
        or '感' in r.get('commitString', ''), r
    print('尾部 n 转 ん ok:', r.get('commitString'))

    r = srv.type('kyouha')
    r = srv.key(vk=VK_BACK)
    assert r.get('compositionString') == 'きょうh', r
    r = srv.key(vk=VK_ESCAPE)
    assert r.get('compositionString') == '' and not r.get('commitString'), r
    print('Backspace/Esc ok')

    srv.close()
    print('\n全部通过 ✓')


if __name__ == '__main__':
    main()
