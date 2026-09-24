#! python3
# -*- coding: utf-8 -*-
"""把日文输入法模块部署到 PIME 并重新注册。

需要管理员权限（写 Program Files + regsvr32），非管理员运行时会自提权。
用法: python install.py
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys

PIME_DIR = r'C:\Program Files (x86)\PIME'
MODULE_DIR = os.path.join(PIME_DIR, 'python', 'input_methods', 'jpime')
HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(HERE, '.venv', 'Scripts', 'python.exe')

MODULE_FILES = ['ime.json', 'jp_ime.py', 'romaji.py', 'converter.py',
                'converter_server.py', 'user_history.py', 'config.py',
                'settings.ps1', 'icon.ico', 'icon_en.ico', 'icon_config.ico',
                'predict_index.pkl', 'jpime-tray.exe']


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    if not os.path.isdir(PIME_DIR):
        sys.exit('未找到 PIME 安装目录: ' + PIME_DIR)
    if not os.path.isfile(VENV_PYTHON):
        sys.exit('未找到虚拟环境 Python: ' + VENV_PYTHON)

    # 0. 如果之前误改过 backends.json，恢复原版
    backends_path = os.path.join(PIME_DIR, 'backends.json')
    if os.path.isfile(backends_path + '.bak'):
        shutil.copy2(backends_path + '.bak', backends_path)
        os.remove(backends_path + '.bak')
        print('已恢复 backends.json')

    # 0. 停掉托盘程序（运行中的 exe 无法覆盖）
    subprocess.run(['taskkill', '/F', '/IM', 'jpime-tray.exe'],
                   capture_output=True)

    # 1. 复制模块文件
    os.makedirs(MODULE_DIR, exist_ok=True)
    for f in MODULE_FILES:
        src = os.path.join(HERE, f)
        if not os.path.isfile(src):
            print('跳过（不存在）', f)
            continue
        shutil.copy2(src, os.path.join(MODULE_DIR, f))
        print('复制', f)

    # 2. 写引擎配置（PIME 自带 32 位 Python 跑不了 MeCab，用 helper 进程）
    #    优先用安装版便携运行时，其次是开发用 venv
    runtime_python = os.path.join(PIME_DIR, 'jpime-runtime', 'python.exe')
    engine_python = runtime_python if os.path.isfile(runtime_python) else VENV_PYTHON
    engine_conf = {
        'python': engine_python,
        'server': os.path.join(MODULE_DIR, 'converter_server.py'),
    }
    for path in (os.path.join(MODULE_DIR, 'engine.json'),
                 os.path.join(HERE, 'engine.json')):
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(engine_conf, fp, ensure_ascii=False, indent=2)
    print('已写 engine.json')

    # 3. 先停掉 PIME（不停会锁住 DLL，替换失败）
    subprocess.run([os.path.join(PIME_DIR, 'PIMELauncher.exe'), '/quit'],
                   capture_output=True)
    import time
    time.sleep(1.5)

    # 4. 如果编译了定制 DLL（现代化候选窗），替换并备份原版。
    #    已被加载的 DLL 不能直接覆盖，但可以改名挪走（Windows 允许）。
    for arch, build_dir in (('x86', 'build32'), ('x64', 'build64')):
        new_dll = os.path.join(HERE, 'PIME-src', build_dir,
                               'PIMETextService', 'Release', 'PIMETextService.dll')
        dst = os.path.join(PIME_DIR, arch, 'PIMETextService.dll')
        if os.path.isfile(new_dll):
            bak = dst + '.orig'
            if os.path.isfile(bak):
                # 已有原版备份，当前文件挪为唯一名字的 .old（改名对锁定的 DLL 也有效）
                old = '%s.old%d' % (dst, int(time.time()))
                os.rename(dst, old)
            else:
                os.rename(dst, bak)
            shutil.copy2(new_dll, dst)
            print('已替换', dst, '（原版备份为 .orig）')

    # 5. 重新注册 TSF DLL（让它发现新模块），再启动
    for arch in ('x86', 'x64'):
        dll = os.path.join(PIME_DIR, arch, 'PIMETextService.dll')
        if os.path.isfile(dll):
            subprocess.run(['regsvr32', '/s', dll], check=True)
            print('已注册', dll)

    # 6. 启用日语 profile（注册在 ja-JP 下），并清理旧的 zh-CN 挂载
    import winreg
    prof = 'DA3AF487-B408-4C4F-B9BE-CD1D1243F703'
    clsid = '35F67E9D-A54D-4177-9697-8B0AB71A9E04'
    up = r'Control Panel\International\User Profile'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, up + r'\ja') as k:
        winreg.SetValueEx(k, '0411:{%s}{%s}' % (clsid, prof), 0,
                          winreg.REG_DWORD, 1)
    for lang in ('zh-CN', 'zh-Hans-CN'):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                up + '\\' + lang, 0,
                                winreg.KEY_ALL_ACCESS) as k:
                winreg.DeleteValue(k, '0804:{%s}{%s}' % (clsid, prof))
        except OSError:
            pass
    print('已在「日语」语言下启用')

    subprocess.Popen([os.path.join(PIME_DIR, 'PIMELauncher.exe')],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 7. 托盘伴侣：注册开机自启并立即启动（唯一托盘图标）
    tray = os.path.join(MODULE_DIR, 'jpime-tray.exe')
    if os.path.isfile(tray):
        with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
            winreg.SetValueEx(k, 'jpime-tray', 0, winreg.REG_SZ, tray)
        subprocess.Popen([tray], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print('托盘程序已启动并注册自启')
    print('完成。')


if __name__ == '__main__':
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', sys.executable, os.path.abspath(__file__), HERE, 1)
    else:
        try:
            with open(os.path.join(HERE, 'install_log.txt'), 'w',
                      encoding='utf-8') as log:
                sys.stdout = log
                sys.stderr = log
                main()
        except Exception:  # noqa: BLE001
            import traceback
            with open(os.path.join(HERE, 'install_log.txt'), 'a',
                      encoding='utf-8') as log:
                traceback.print_exc(file=log)
            raise
