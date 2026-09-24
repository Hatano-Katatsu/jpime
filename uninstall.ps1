# jpime uninstaller. Removes module, runtime, dlls, registrations.
$ErrorActionPreference = 'Continue'
$log = Join-Path $env:TEMP 'jpime_uninstall_log.txt'
function Log($msg) { "$msg" | Tee-Object -FilePath $log -Append }

# self-elevate
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$($MyInvocation.MyCommand.Path)`""
    exit
}

$pimeDir = 'C:\Program Files (x86)\PIME'
$clsid = '{35F67E9D-A54D-4177-9697-8B0AB71A9E04}'
$prof  = '{DA3AF487-B408-4C4F-B9BE-CD1D1243F703}'

# 1. stop backend and tray companion
$launcher = Join-Path $pimeDir 'PIMELauncher.exe'
if (Test-Path $launcher) { & $launcher /quit 2>$null | Out-Null; Start-Sleep -Seconds 2 }
& taskkill /F /IM jpime-tray.exe 2>$null | Out-Null
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'jpime-tray' -Force -ErrorAction SilentlyContinue

# 2. restore original dlls and launcher (rename works on locked files)
foreach ($arch in 'x86', 'x64') {
    $dll = Join-Path $pimeDir "$arch\PIMETextService.dll"
    $bak = "$dll.orig"
    if (Test-Path $bak) {
        if (Test-Path $dll) { Rename-Item $dll "$dll.jpold" -Force }
        Rename-Item $bak $dll -Force
        Log "dll restored: $arch"
    }
}
$exeBak = "$launcher.orig"
if (Test-Path $exeBak) {
    if (Test-Path $launcher) { Rename-Item $launcher "$launcher.jpold" -Force }
    Rename-Item $exeBak $launcher -Force
    Log 'launcher restored'
}

# 3. remove TSF profile registration (both old zh-CN and current ja-JP)
foreach ($hive in 'HKLM:\SOFTWARE\Microsoft\CTF\TIP', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\CTF\TIP') {
    foreach ($langId in '0x00000411', '0x00000804') {
        $key = "$hive\$clsid\LanguageProfile\$langId\$prof"
        if (Test-Path $key) { Remove-Item $key -Recurse -Force; Log "profile removed: $key" }
    }
}

# 4. remove from user's enabled input methods
$valJa = "0411:$clsid$prof"
$valZh = "0804:$clsid$prof"
foreach ($lang in 'ja', 'zh-Hans-CN', 'zh-CN') {
    $p = "HKCU:\Control Panel\International\User Profile\$lang"
    if (Test-Path $p) {
        Remove-ItemProperty -Path $p -Name $valJa -Force -ErrorAction SilentlyContinue
        Remove-ItemProperty -Path $p -Name $valZh -Force -ErrorAction SilentlyContinue
    }
}

# 5. remove files
foreach ($d in @("$pimeDir\python\input_methods\jpime", "$pimeDir\jpime-runtime")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force; Log "removed: $d" }
}
$self = Join-Path $pimeDir 'jpime-uninstall.ps1'

# 6. remove uninstall registry entry
Remove-Item 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\jpime' -Recurse -Force -ErrorAction SilentlyContinue

# 7. ask about user data (learned words, config)
Add-Type -AssemblyName PresentationFramework
$ans = [System.Windows.MessageBox]::Show('是否同时删除用户数据（选词学习记录、快捷键配置）？', '日文输入法卸载', 'YesNo', 'Question')
if ($ans -eq 'Yes') {
    Remove-Item "$env:APPDATA\jpime" -Recurse -Force -ErrorAction SilentlyContinue
    Log 'user data removed'
}

# 8. restart launcher (PIME 本体保留，可单独卸载)
if (Test-Path $launcher) { Start-Process $launcher }
Remove-Item $self -Force -ErrorAction SilentlyContinue
[System.Windows.MessageBox]::Show('卸载完成。如不再需要 PIME 框架本身，可在系统设置的应用列表里卸载 PIME。', '日文输入法卸载') | Out-Null
Log 'uninstall done'
