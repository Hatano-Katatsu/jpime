# 移除 PIME 自带的新酷音(chewing)模块,保留 jpime 与 PIME 本体
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$tipClsid = '{35F67E9D-A54D-4177-9697-8B0AB71A9E04}'
$chewGuid = '{F80736AA-28DB-423A-92C9-5540F501C939}'

# 1. 停掉 PIME 启动器(占用文件)
Get-Process PIMELauncher -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

# 2. 删除新酷音的注册表项(只删 chewing 的 profile,不动共享 CLSID 和 jpime)
$roots = @('HKLM:\SOFTWARE\Microsoft\CTF\TIP', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\CTF\TIP')
foreach ($root in $roots) {
  $tipPath = Join-Path $root $tipClsid
  Get-ChildItem $tipPath -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -eq $chewGuid } |
    ForEach-Object {
      Remove-Item $_.PSPath -Recurse -Force -ErrorAction Continue
      Write-Output ("删除注册表: " + $_.PSPath)
    }
}

# 3. 删除 chewing 模块文件夹
$chewDir = 'C:\Program Files (x86)\PIME\python\input_methods\chewing'
if (Test-Path $chewDir) {
  Remove-Item $chewDir -Recurse -Force -ErrorAction Continue
  if (Test-Path $chewDir) { Write-Output "警告: chewing 文件夹未能完全删除(可能权限不足或文件占用)" }
  else { Write-Output "已删除: $chewDir" }
} else { Write-Output "chewing 文件夹不存在,跳过" }

# 4. 重启 PIME 启动器
$launcher = 'C:\Program Files (x86)\PIME\PIMELauncher.exe'
if (Test-Path $launcher) { Start-Process $launcher; Write-Output "已重启 PIMELauncher" }

# 5. 验证
$left = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\CTF\TIP' -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.PSChildName -eq $chewGuid }
if ($left) { Write-Output "仍有残留注册表项:"; $left | ForEach-Object { Write-Output $_.PSPath } }
else { Write-Output "注册表已清理干净" }
