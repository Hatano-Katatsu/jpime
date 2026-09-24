# jpime 安装脚本（仓库分发版）。最终用户用：右键 -> 使用 PowerShell 运行，批准一次 UAC。
# 大件（PIME 本体 / 便携 Python / MeCab / mozcpy 词典）联网下载；本脚本可重复运行，已装组件自动跳过。
# 本文件必须保存为 UTF-8 with BOM（PS5.1 无 BOM 会把中文读乱）。
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # PS5.1 的 Invoke-WebRequest 进度条会拖慢下载几十倍
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $env:TEMP 'jpime_install_log.txt'
function Log($msg) { "$(Get-Date -Format 'HH:mm:ss') $msg" | Tee-Object -FilePath $log -Append }

# 0. 自提权
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$($MyInvocation.MyCommand.Path)`""
    exit
}

$pimeDir = 'C:\Program Files (x86)\PIME'
$modDir  = Join-Path $pimeDir 'python\input_methods\jpime'
$rtDir   = Join-Path $pimeDir 'jpime-runtime'
$spDir   = Join-Path $rtDir 'site-packages'
$dl      = Join-Path $env:TEMP 'jpime_dl'
New-Item -ItemType Directory -Force -Path $dl | Out-Null

# 依次尝试多个 URL 下载，全部失败才抛错
function Get-File($urls, $outPath) {
    foreach ($u in $urls) {
        try {
            Log "下载 $u"
            Invoke-WebRequest -Uri $u -OutFile $outPath -UseBasicParsing -TimeoutSec 900
            return
        } catch {
            Log "下载失败: $($_.Exception.Message)"
            if (Test-Path $outPath) { Remove-Item $outPath -Force }
        }
    }
    throw "下载失败（所有源都不可用）: $outPath"
}

# 从 PyPI 解析文件名匹配 $pattern 的下载地址；PyPI JSON 不可用时退回阿里云 simple 索引
function Resolve-PyPIUrl($project, $pattern) {
    try {
        $j = Invoke-RestMethod -Uri "https://pypi.org/pypi/$project/json" -TimeoutSec 60
        $ver = $j.info.version
        $u = $j.releases.$ver | Where-Object { $_.filename -match $pattern } | Select-Object -First 1
        if ($u) { return $u.url }
    } catch { Log "PyPI JSON 不可用: $($_.Exception.Message)" }
    $base = "https://mirrors.aliyun.com/pypi/simple/$project/"
    $html = (Invoke-WebRequest -Uri $base -UseBasicParsing -TimeoutSec 60).Content
    $hit = [regex]::Matches($html, 'href="([^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } |
        Where-Object { $_ -match $pattern } | Select-Object -Last 1
    if (-not $hit) { throw "找不到 $project 匹配 $pattern 的文件" }
    return (New-Object System.Uri((New-Object System.Uri($base)), $hit)).GetLeftPart('Path')
}

function Swap-Binary($src, $dst) {
    # 内容相同则跳过（幂等）；否则把旧文件改名挪走（对锁定的 DLL/EXE 也有效）再复制
    if ((Test-Path $dst) -and
        (Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash) {
        Log "已是最新，跳过: $dst"
        return
    }
    if (Test-Path $dst) {
        $bak = "$dst.orig"
        if (Test-Path $bak) { $bak = "$dst.old$([int](Get-Date -UFormat %s))" }
        Rename-Item $dst (Split-Path -Leaf $bak) -Force
    }
    Copy-Item $src $dst -Force
    Log "已替换: $dst"
}

try {
    # 1. PIME 框架本体（未安装才装）
    $launcher = Join-Path $pimeDir 'PIMELauncher.exe'
    if (-not (Test-Path $launcher)) {
        $setup = Join-Path $dl 'PIME-setup.exe'
        Get-File @('https://github.com/EasyIME/PIME/releases/download/v1.3.0-stable/PIME-1.3.0-stable-setup.exe',
                   'https://mirror.ghproxy.com/https://github.com/EasyIME/PIME/releases/download/v1.3.0-stable/PIME-1.3.0-stable-setup.exe') $setup
        Log '静默安装 PIME...'
        Start-Process -FilePath $setup -ArgumentList '/S' -Wait
        if (-not (Test-Path $launcher)) { throw 'PIME 安装失败' }
    } else {
        Log 'PIME 已安装，跳过'
    }

    # 2. 停掉后端和托盘（运行中的文件无法覆盖；改名挪走前也先停干净）
    & $launcher /quit 2>$null | Out-Null
    Start-Sleep -Seconds 2
    Get-Process jpime-tray -ErrorAction SilentlyContinue | Stop-Process -Force

    # 3. 复制模块文件
    New-Item -ItemType Directory -Force -Path $modDir | Out-Null
    foreach ($f in 'ime.json','jp_ime.py','romaji.py','converter.py','converter_server.py',
                   'user_history.py','config.py','settings.ps1','icon.ico','icon_en.ico',
                   'icon_config.ico','jpime-tray.exe') {
        Copy-Item (Join-Path $repo $f) $modDir -Force
    }
    Log '模块文件已复制'

    # 4. 替换 PIMELauncher 和 x86/x64 定制 DLL（原版备份为 .orig，卸载时恢复）
    Swap-Binary (Join-Path $repo 'bin\PIMELauncher.exe') $launcher
    Swap-Binary (Join-Path $repo 'bin\PIMETextService-x86.dll') (Join-Path $pimeDir 'x86\PIMETextService.dll')
    Swap-Binary (Join-Path $repo 'bin\PIMETextService-x64.dll') (Join-Path $pimeDir 'x64\PIMETextService.dll')

    # 5. 便携 Python 3.12 运行时 + MeCab + mozcpy（PIME 自带的 32 位 Py3.8 装不了 MeCab）
    $rtPy = Join-Path $rtDir 'python.exe'
    if (-not (Test-Path $rtPy)) {
        $zip = Join-Path $dl 'python-embed.zip'
        Get-File @('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',
                   'https://mirrors.huaweicloud.com/python/3.12.10/python-3.12.10-embed-amd64.zip') $zip
        Expand-Archive -Path $zip -DestinationPath $rtDir -Force
        Log '便携 Python 已解压'
    } else {
        Log '便携 Python 已存在，跳过'
    }
    New-Item -ItemType Directory -Force -Path $spDir | Out-Null

    if (-not (Test-Path (Join-Path $spDir 'MeCab\libmecab.dll'))) {
        $whlUrl = Resolve-PyPIUrl 'mecab-python3' 'cp312.*win_amd64\.whl'
        $whl = Join-Path $dl 'mecab.zip'   # Expand-Archive 只认 .zip 扩展名
        Get-File @($whlUrl) $whl
        $whlX = Join-Path $dl 'mecab_x'
        if (Test-Path $whlX) { Remove-Item $whlX -Recurse -Force }
        Expand-Archive -Path $whl -DestinationPath $whlX -Force
        # 按 pip 的布局放：包文件直接进 site-packages；.data/data/lib/site-packages 里的（libmecab.dll）也要并进去
        Get-ChildItem $whlX | Where-Object { $_.Name -notlike '*.dist-info' -and $_.Name -notlike '*.data' } |
            Copy-Item -Destination $spDir -Recurse -Force
        $dataLib = Get-ChildItem $whlX -Directory -Filter '*.data' |
            ForEach-Object { Join-Path $_.FullName 'data\lib\site-packages' } |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dataLib) { Copy-Item (Join-Path $dataLib '*') $spDir -Recurse -Force }
        Log 'MeCab 已装入 site-packages'
    } else {
        Log 'MeCab 已存在，跳过'
    }

    if (-not (Test-Path (Join-Path $spDir 'mozcpy\dic'))) {
        $sdUrl = Resolve-PyPIUrl 'mozcpy' '\.tar\.gz'
        $sd = Join-Path $dl 'mozcpy.tar.gz'
        Get-File @($sdUrl) $sd
        $sdX = Join-Path $dl 'mozcpy_x'
        if (Test-Path $sdX) { Remove-Item $sdX -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $sdX | Out-Null
        & tar -xzf $sd -C $sdX
        if ($LASTEXITCODE -ne 0) { throw 'mozcpy sdist 解压失败' }
        $pkg = Get-ChildItem $sdX -Recurse -Directory -Filter 'mozcpy' |
            Where-Object { Test-Path (Join-Path $_.FullName 'dic') } | Select-Object -First 1
        if (-not $pkg) { throw 'mozcpy sdist 里没找到带 dic 的包目录' }
        Copy-Item $pkg.FullName $spDir -Recurse -Force
        Log 'mozcpy（含词典）已装入 site-packages'
    } else {
        Log 'mozcpy 已存在，跳过'
    }

    # 6. 前缀联想索引（模块目录没有才现场构建）
    if (-not (Test-Path (Join-Path $modDir 'predict_index.pkl'))) {
        $work = Join-Path $env:TEMP 'jpime_predict'
        if (Test-Path $work) { Remove-Item $work -Recurse -Force }
        New-Item -ItemType Directory -Force -Path (Join-Path $work 'dict_src') | Out-Null
        foreach ($i in 0..9) {
            Get-File @("https://gitee.com/mirrors_google/mozc/raw/master/src/data/dictionary_oss/dictionary0$i.txt") `
                     (Join-Path $work "dict_src\dictionary0$i.txt")
        }
        Push-Location $work
        try {
            & $rtPy (Join-Path $repo 'build_predict_index.py') | Tee-Object -FilePath $log -Append
            if ($LASTEXITCODE -ne 0) { throw 'predict_index 构建失败' }
        } finally { Pop-Location }
        Copy-Item (Join-Path $work 'predict_index.pkl') $modDir -Force
        Remove-Item $work -Recurse -Force
        Log 'predict_index.pkl 已构建'
    } else {
        Log 'predict_index.pkl 已存在，跳过'
    }

    # 7. engine.json -> 便携运行时（必须无 BOM，Python json 库不认 BOM）
    $engine = @{
        python = $rtPy
        server = Join-Path $modDir 'converter_server.py'
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText((Join-Path $modDir 'engine.json'), $engine,
                                   (New-Object System.Text.UTF8Encoding($false)))
    Log 'engine.json 已写入'

    # 8. 注册 TSF DLL
    foreach ($arch in 'x86', 'x64') {
        $dll = Join-Path $pimeDir "$arch\PIMETextService.dll"
        if (Test-Path $dll) { & regsvr32 /s $dll; Log "已注册 $arch" }
    }

    # 9. 在「日语」语言下启用本输入法；清理旧的 zh-CN 挂载
    $clsid  = '{35F67E9D-A54D-4177-9697-8B0AB71A9E04}'
    $jpProf = '{DA3AF487-B408-4C4F-B9BE-CD1D1243F703}'
    $p = 'HKCU:\Control Panel\International\User Profile\ja'
    New-Item -Path $p -Force | Out-Null
    New-ItemProperty -Path $p -Name "0411:$clsid$jpProf" -Value 1 -PropertyType DWord -Force | Out-Null
    foreach ($lang in 'zh-Hans-CN', 'zh-CN') {
        $zp = "HKCU:\Control Panel\International\User Profile\$lang"
        if (Test-Path $zp) {
            Remove-ItemProperty -Path $zp -Name "0804:$clsid$jpProf" -Force -ErrorAction SilentlyContinue
        }
    }
    Log '已在「日语」语言下启用'

    # 10. 托盘开机自启（HKCU，免管理员 hive）
    $tray = Join-Path $modDir 'jpime-tray.exe'
    New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' `
        -Name 'jpime-tray' -Value $tray -PropertyType String -Force | Out-Null

    # 11. 系统「应用和功能」卸载入口 + 卸载脚本
    Copy-Item (Join-Path $repo 'uninstall.ps1') (Join-Path $pimeDir 'jpime-uninstall.ps1') -Force
    $uninst = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\jpime'
    New-Item -Path $uninst -Force | Out-Null
    Set-ItemProperty $uninst 'DisplayName' '日文输入法（中文式选词）'
    Set-ItemProperty $uninst 'UninstallString' "powershell -NoProfile -ExecutionPolicy Bypass -File `"$pimeDir\jpime-uninstall.ps1`""
    Set-ItemProperty $uninst 'DisplayIcon' (Join-Path $modDir 'icon.ico')
    Set-ItemProperty $uninst 'Publisher' 'jpime'
    Log '卸载入口已注册'

    # 12. 启动后端 + 托盘
    Start-Process $launcher
    if (Test-Path $tray) { Start-Process $tray }
    Log '安装完成'
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('安装完成！如果输入法列表里还没有它，注销重登一次即可。', '日文输入法（中文式选词）') | Out-Null
} catch {
    Log "安装失败: $($_.Exception.Message)"
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("安装失败：$($_.Exception.Message)`n日志：$log", '日文输入法（中文式选词）', 'OK', 'Error') | Out-Null
    exit 1
}
