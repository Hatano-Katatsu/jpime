# -*- coding: utf-8 -*-
"""验证【已安装】的 jpime：用 PIME 自带 32 位 Python 跑 server.py + 已安装模块，
engine.json 指向已安装的便携运行时（与 install.ps1 第 7 步一致）。"""
import json
import os
import shutil
import subprocess
import sys

PIME_PY = r'C:\Program Files (x86)\PIME\python'
MOD_INSTALLED = os.path.join(PIME_PY, 'input_methods', 'jpime')
RT_PY = r'C:\Program Files (x86)\PIME\jpime-runtime\python.exe'
HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.join(HERE, '.pime_installed_test')
GUID = '{DA3AF487-B408-4C4F-B9BE-CD1D1243F703}'

VK_BACK, VK_RETURN, VK_ESCAPE, VK_SPACE, VK_DOWN = 0x08, 0x0D, 0x1B, 0x20, 0x28


def setup_sandbox():
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)
    shutil.copytree(PIME_PY, os.path.join(SANDBOX, 'python'),
                    ignore=shutil.ignore_patterns('__pycache__'))
    mod_dir = os.path.join(SANDBOX, 'python', 'input_methods', 'jpime')
    # 用已安装模块覆盖 sandbox 里的（确保测的是装好的版本）
    for f in os.listdir(MOD_INSTALLED):
        if f.endswith('.py') or f in ('ime.json', 'engine.json', 'config.py',
                                      'predict_index.pkl'):
            shutil.copy2(os.path.join(MOD_INSTALLED, f), os.path.join(mod_dir, f))
    with open(os.path.join(mod_dir, 'engine.json'), 'w', encoding='utf-8') as fp:
        json.dump({'python': RT_PY, 'server': os.path.join(mod_dir, 'converter_server.py')}, fp)


class Server:
    def __init__(self):
        env = dict(os.environ, PYTHONIOENCODING='utf-8:ignore')
        self.proc = subprocess.Popen(
            [os.path.join(SANDBOX, 'python', 'python3', 'python.exe'), 'server.py'],
            cwd=os.path.join(SANDBOX, 'python'),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, encoding='utf-8')

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
            print('[server]', line.rstrip())

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
    assert os.path.isfile(RT_PY), '未找到便携运行时: ' + RT_PY
    setup_sandbox()
    srv = Server()

    r = srv.request({'method': 'init', 'seqNum': 0, 'id': GUID,
                     'isWindows8Above': True, 'isMetroApp': False,
                     'isUiLess': False, 'isConsole': False})
    assert r.get('success'), r
    print('init ok')

    r = srv.request({'method': 'onActivate', 'seqNum': 1, 'isKeyboardOpen': True})
    assert r.get('success'), r

    r = srv.type('kyou')
    assert r.get('compositionString') == 'きょう', r
    cands = r.get('candidateList', [])
    print('候选:', cands[:5])
    assert cands and cands[0] == '今日', cands

    r = srv.key('1')
    assert r.get('commitString') == '今日', r
    print('数字键选词 ok: 今日')

    srv.close()
    shutil.rmtree(SANDBOX, ignore_errors=True)
    print('\n已安装后端验证通过 ✓')


if __name__ == '__main__':
    main()
