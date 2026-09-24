$ErrorActionPreference = 'Stop'
$log = 'D:\kimi\jpime\swap_pime_launcher.log'
function Log($msg) { "$(Get-Date -Format 'HH:mm:ss') $msg" | Out-File -Append -Encoding utf8 $log }
'' | Out-File -Encoding utf8 $log

$target = 'C:\Program Files (x86)\PIME\PIMELauncher.exe'
$newExe = 'D:\kimi\jpime\PIME-src\build32-launcher\PIMELauncher\Release\PIMELauncher.exe'
$ts = Get-Date -Format 'yyyyMMddHHmmss'
$backup = "$target.old$ts"

try {
    # ask the running launcher to quit (elevated, so UIPI does not block it)
    Log 'send /quit'
    Start-Process -FilePath $target -ArgumentList '/quit'
    Start-Sleep -Seconds 3
    $proc = Get-Process -Name PIMELauncher -ErrorAction SilentlyContinue
    if ($proc) {
        Log "still running (pid $($proc.Id -join ',')), force kill"
        $proc | Stop-Process -Force
        Start-Sleep -Seconds 2
    } else {
        Log 'launcher exited'
    }

    Log "rename to $backup"
    Rename-Item -Path $target -NewName (Split-Path $backup -Leaf)
    Log 'copy new exe'
    Copy-Item -Path $newExe -Destination $target
    $sig = (Get-Item $target).Length
    Log "DONE size=$sig"
} catch {
    Log "ERROR: $_"
    exit 1
}
