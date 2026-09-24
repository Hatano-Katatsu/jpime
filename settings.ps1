# jpime settings GUI (WPF, modern style matching the candidate window).
# Key capture: click a box and press the actual keys. Edits %APPDATA%\jpime\config.json
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$cfgDir = Join-Path $env:APPDATA 'jpime'
$cfgPath = Join-Path $cfgDir 'config.json'

$actions = @(
    @('commit_kana',           '上屏原始假名'),
    @('cancel',                '取消输入'),
    @('commit_full_katakana',  '上屏全角片假名'),
    @('commit_half_katakana',  '上屏半角片假名'),
    @('page_up',               '候选上一页'),
    @('page_down',             '候选下一页'),
    @('cursor_up',             '候选光标上移'),
    @('cursor_down',           '候选光标下移'),
    @('toggle_english',        '单击切换英文模式')
)

$defaults = @{
    commit_kana = @('return'); cancel = @('escape')
    commit_full_katakana = @('tab'); commit_half_katakana = @('oem3')
    page_up = @(',', '<', 'prior'); page_down = @('.', '>', 'next')
    cursor_up = @('up'); cursor_down = @('down'); toggle_english = @('shift')
}

$current = @{}
foreach ($a in $actions) { $current[$a[0]] = $defaults[$a[0]] }
$script:perRow = 9   # 候选窗每排个数：9=横排，1=竖排
$script:jpPunct = $true   # 日文标点映射（, -> 、  . -> 。  等）
if (Test-Path $cfgPath) {
    try {
        $j = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($a in $actions) {
            $v = $j.keymap.($a[0])
            if ($v) { $current[$a[0]] = @($v) }
        }
        if ($j.candPerRow -ge 1) { $script:perRow = [int]$j.candPerRow }
        if ($null -ne $j.japanese_punct) { $script:jpPunct = [bool]$j.japanese_punct }
    } catch {}
}

# WPF Key name -> config key name (config.py 的 _SPECIAL_KEYS)
$vkMap = @{
    Back = 'back'; Tab = 'tab'; Return = 'return'; Escape = 'escape'
    Space = 'space'; PageUp = 'prior'; PageDown = 'next'; End = 'end'; Home = 'home'
    Left = 'left'; Up = 'up'; Right = 'right'; Down = 'down'; Oem3 = 'oem3'
    LeftShift = 'shift'; RightShift = 'shift'; LeftCtrl = 'control'; RightCtrl = 'control'
}
for ($i = 1; $i -le 12; $i++) { $vkMap['F' + $i] = 'f' + $i }

# ---- style tokens（与候选窗一致）----
$cBg       = [Windows.Media.ColorConverter]::ConvertFromString('#FFFFFF')
$cBorder   = [Windows.Media.ColorConverter]::ConvertFromString('#E0E0E0')
$cText     = [Windows.Media.ColorConverter]::ConvertFromString('#1B1B1B')
$cSub      = [Windows.Media.ColorConverter]::ConvertFromString('#6D6D6D')
$cHover    = [Windows.Media.ColorConverter]::ConvertFromString('#E5E5E5')
$cFocus    = [Windows.Media.ColorConverter]::ConvertFromString('#9E9E9E')
$brush = { param($c) $b = New-Object Windows.Media.SolidColorBrush $c; $b.Freeze(); $b }
$brBg = & $brush $cBg; $brBorder = & $brush $cBorder; $brText = & $brush $cText
$brSub = & $brush $cSub; $brHover = & $brush $cHover; $brFocus = & $brush $cFocus
$fontUi = New-Object Windows.Media.FontFamily 'Microsoft YaHei UI'
$fontMono = New-Object Windows.Media.FontFamily 'Consolas, Microsoft YaHei UI'

function Append-Key($box, $name) {
    $tokens = @($box.Tag.tokens | Where-Object { $_ })
    if ($tokens -notcontains $name) { $tokens += $name }
    $box.Tag.tokens = $tokens
    $box.Child.Text = ($tokens -join '  ')
}

# ---- window shell ----
$win = New-Object Windows.Window
$win.WindowStyle = 'None'
$win.AllowsTransparency = $true
$win.Background = [Windows.Media.Brushes]::Transparent
$win.Width = 500
$win.SizeToContent = 'Height'
$win.WindowStartupLocation = 'CenterScreen'
$win.ResizeMode = 'NoResize'
$win.FontFamily = $fontUi
$win.FontSize = 13

$root = New-Object Windows.Controls.Border
$root.Background = $brBg
$root.CornerRadius = '8'
$root.BorderBrush = $brBorder
$root.BorderThickness = '1'
$root.Effect = New-Object Windows.Media.Effects.DropShadowEffect
$root.Effect.Color = [Windows.Media.Colors]::Black
$root.Effect.BlurRadius = 18
$root.Effect.ShadowDepth = 0
$root.Effect.Opacity = 0.18
$win.Content = $root

$stack = New-Object Windows.Controls.StackPanel
$root.Child = $stack

# title bar
$titleBar = New-Object Windows.Controls.Grid
$titleBar.Height = 44
$titleBar.Margin = '16,10,10,0'
$titleText = New-Object Windows.Controls.TextBlock
$titleText.Text = '日文输入法  设置'
$titleText.FontSize = 15
$titleText.FontWeight = 'SemiBold'
$titleText.Foreground = $brText
$titleText.VerticalAlignment = 'Center'
$btnClose = New-Object Windows.Controls.Button
$btnClose.Content = '✕'
$btnClose.Width = 32; $btnClose.Height = 32
$btnClose.HorizontalAlignment = 'Right'
$btnClose.Background = [Windows.Media.Brushes]::Transparent
$btnClose.Foreground = $brSub
$btnClose.BorderThickness = '0'
$btnClose.Cursor = 'Hand'
$btnClose.Add_Click({ $win.Close() })
$btnClose.Add_MouseEnter({ $btnClose.Foreground = $brText })
$btnClose.Add_MouseLeave({ $btnClose.Foreground = $brSub })
$titleBar.Children.Add($titleText) | Out-Null
$titleBar.Children.Add($btnClose) | Out-Null
$titleBar.Add_MouseLeftButtonDown({ $win.DragMove() })
$stack.Children.Add($titleBar) | Out-Null

$tip = New-Object Windows.Controls.TextBlock
$tip.Text = '点击输入框后直接按键录入（可录多个）；Delete 清空该条；Shift / Ctrl 单按也可录入。'
$tip.Foreground = $brSub
$tip.FontSize = 11
$tip.Margin = '20,2,20,10'
$tip.TextWrapping = 'Wrap'
$stack.Children.Add($tip) | Out-Null

# ---- capture rows ----
$boxes = @{}
foreach ($a in $actions) {
    $row = New-Object Windows.Controls.Grid
    $row.Margin = '20,4,20,4'
    $col1 = New-Object Windows.Controls.ColumnDefinition; $col1.Width = '150'
    $col2 = New-Object Windows.Controls.ColumnDefinition; $col2.Width = '*'
    $row.ColumnDefinitions.Add($col1); $row.ColumnDefinitions.Add($col2)

    $lbl = New-Object Windows.Controls.TextBlock
    $lbl.Text = $a[1]
    $lbl.Foreground = $brText
    $lbl.VerticalAlignment = 'Center'
    [Windows.Controls.Grid]::SetColumn($lbl, 0)

    $box = New-Object Windows.Controls.Border
    $box.Height = 32
    $box.Background = $brBg
    $box.BorderBrush = $brBorder
    $box.BorderThickness = '1'
    $box.CornerRadius = '4'
    $box.Cursor = 'Hand'
    $box.Focusable = $true
    $tb = New-Object Windows.Controls.TextBlock
    $tb.Text = ($current[$a[0]] -join '  ')
    $tb.FontFamily = $fontMono
    $tb.Foreground = $brText
    $tb.Margin = '10,0,10,0'
    $tb.VerticalAlignment = 'Center'
    $box.Child = $tb
    $box.Tag = @{ tokens = @($current[$a[0]]); pending = $null }
    [Windows.Controls.Grid]::SetColumn($box, 1)

    $box.Add_GotFocus({ param($s, $e) $s.BorderBrush = $brFocus })
    $box.Add_LostFocus({ param($s, $e) $s.BorderBrush = $brBorder; $s.Tag.pending = $null })
    $box.Add_MouseLeftButtonDown({ param($s, $e) [Windows.Input.Keyboard]::Focus($s) | Out-Null })

    $box.Add_PreviewKeyDown({
        param($s, $e)
        $code = $e.Key.ToString()
        if ($code -eq 'Delete') {
            $s.Tag.tokens = @(); $s.Child.Text = ''
            $e.Handled = $true; return
        }
        $name = $vkMap[$code]
        if ($name) {
            $e.Handled = $true
            if ($name -eq 'shift' -or $name -eq 'control') {
                $s.Tag.pending = $name   # 修饰键：等 KeyUp 确认「单按」
            } else {
                $s.Tag.pending = $null
                Append-Key $s $name
            }
        }
    })

    $box.Add_PreviewTextInput({
        param($s, $e)
        $s.Tag.pending = $null
        $ch = $e.Text
        if ($ch -and -not [char]::IsControl($ch[0])) {
            Append-Key $s $ch.ToLower()
        }
        $e.Handled = $true
    })

    $box.Add_KeyUp({
        param($s, $e)
        $code = $e.Key.ToString()
        if (($code -eq 'LeftShift' -or $code -eq 'RightShift' -or
             $code -eq 'LeftCtrl' -or $code -eq 'RightCtrl') -and $s.Tag.pending) {
            Append-Key $s $s.Tag.pending
            $s.Tag.pending = $null
        }
    })

    $row.Children.Add($lbl) | Out-Null
    $row.Children.Add($box) | Out-Null
    $stack.Children.Add($row) | Out-Null
    $boxes[$a[0]] = $box
}

# ---- 候选窗排列：横排/竖排分段开关 ----
$layoutRow = New-Object Windows.Controls.Grid
$layoutRow.Margin = '20,10,20,4'
$lcol1 = New-Object Windows.Controls.ColumnDefinition; $lcol1.Width = '150'
$lcol2 = New-Object Windows.Controls.ColumnDefinition; $lcol2.Width = '*'
$layoutRow.ColumnDefinitions.Add($lcol1); $layoutRow.ColumnDefinitions.Add($lcol2)

$layoutLbl = New-Object Windows.Controls.TextBlock
$layoutLbl.Text = '候选窗排列'
$layoutLbl.Foreground = $brText
$layoutLbl.VerticalAlignment = 'Center'
[Windows.Controls.Grid]::SetColumn($layoutLbl, 0)

$segTrack = New-Object Windows.Controls.Border
$segTrack.Background = [Windows.Media.Brushes]::WhiteSmoke
$segTrack.BorderBrush = $brBorder
$segTrack.BorderThickness = '1'
$segTrack.CornerRadius = '4'
$segTrack.Height = 32
$segTrack.Padding = '3'
$segPanel = New-Object Windows.Controls.StackPanel
$segPanel.Orientation = 'Horizontal'
$segTrack.Child = $segPanel
[Windows.Controls.Grid]::SetColumn($segTrack, 1)

$segH = New-Object Windows.Controls.Border  # 横排
$segV = New-Object Windows.Controls.Border  # 竖排
foreach ($seg in @($segH, $segV)) {
    $seg.Width = 110
    $seg.CornerRadius = '3'
    $seg.Cursor = 'Hand'
    $segText = New-Object Windows.Controls.TextBlock
    $segText.HorizontalAlignment = 'Center'
    $segText.VerticalAlignment = 'Center'
    $seg.Child = $segText
    $segPanel.Children.Add($seg) | Out-Null
}
$segH.Child.Text = '横排（一排 9 个）'
$segV.Child.Text = '竖排（一排 1 个）'

$script:updateSeg = {
    if ($script:perRow -le 1) {
        $segV.Background = [Windows.Media.Brushes]::White
        $segV.Child.Foreground = $brText
        $segV.Child.FontWeight = 'SemiBold'
        $segH.Background = [Windows.Media.Brushes]::Transparent
        $segH.Child.Foreground = $brSub
        $segH.Child.FontWeight = 'Normal'
    } else {
        $segH.Background = [Windows.Media.Brushes]::White
        $segH.Child.Foreground = $brText
        $segH.Child.FontWeight = 'SemiBold'
        $segV.Background = [Windows.Media.Brushes]::Transparent
        $segV.Child.Foreground = $brSub
        $segV.Child.FontWeight = 'Normal'
    }
}
$segH.Add_MouseLeftButtonDown({ $script:perRow = 9; & $script:updateSeg })
$segV.Add_MouseLeftButtonDown({ $script:perRow = 1; & $script:updateSeg })
& $script:updateSeg

$layoutRow.Children.Add($layoutLbl) | Out-Null
$layoutRow.Children.Add($segTrack) | Out-Null
$stack.Children.Add($layoutRow) | Out-Null

# ---- 日文标点开关 ----
$punctRow = New-Object Windows.Controls.Grid
$punctRow.Margin = '20,10,20,4'
$pcol1 = New-Object Windows.Controls.ColumnDefinition; $pcol1.Width = '150'
$pcol2 = New-Object Windows.Controls.ColumnDefinition; $pcol2.Width = '*'
$punctRow.ColumnDefinitions.Add($pcol1); $punctRow.ColumnDefinitions.Add($pcol2)

$punctLbl = New-Object Windows.Controls.TextBlock
$punctLbl.Text = '标点'
$punctLbl.Foreground = $brText
$punctLbl.VerticalAlignment = 'Center'
[Windows.Controls.Grid]::SetColumn($punctLbl, 0)

$punctCb = New-Object Windows.Controls.CheckBox
$punctCb.Content = '使用日文标点（, → 、   . → 。   [ → 「  等）'
$punctCb.Foreground = $brText
$punctCb.VerticalAlignment = 'Center'
$punctCb.VerticalContentAlignment = 'Center'
$punctCb.IsChecked = $script:jpPunct
[Windows.Controls.Grid]::SetColumn($punctCb, 1)

$punctRow.Children.Add($punctLbl) | Out-Null
$punctRow.Children.Add($punctCb) | Out-Null
$stack.Children.Add($punctRow) | Out-Null

# ---- buttons ----
$btnRow = New-Object Windows.Controls.StackPanel
$btnRow.Orientation = 'Horizontal'
$btnRow.HorizontalAlignment = 'Right'
$btnRow.Margin = '20,14,20,16'

function New-StyledButton($text, $primary) {
    $b = New-Object Windows.Controls.Button
    $b.Content = $text
    $b.Height = 32; $b.MinWidth = 88
    $b.Margin = '8,0,0,0'
    $b.Cursor = 'Hand'
    $b.FontFamily = $fontUi; $b.FontSize = 12
    $template = [Windows.Markup.XamlReader]::Parse(@"
<ControlTemplate xmlns='http://schemas.microsoft.com/winfx/2006/xaml/presentation' xmlns:x='http://schemas.microsoft.com/winfx/2006/xaml' TargetType='Button'>
  <Border x:Name='bd' CornerRadius='4' Padding='14,0'
          Background='$(if ($primary) {'#1B1B1B'} else {'#FFFFFF'})'
          BorderBrush='$(if ($primary) {'#1B1B1B'} else {'#E0E0E0'})'
          BorderThickness='1'>
    <ContentPresenter HorizontalAlignment='Center' VerticalAlignment='Center'/>
  </Border>
  <ControlTemplate.Triggers>
    <Trigger Property='IsMouseOver' Value='True'>
      <Setter TargetName='bd' Property='Background'
              Value='$(if ($primary) {'#3A3A3A'} else {'#E5E5E5'})'/>
    </Trigger>
  </ControlTemplate.Triggers>
</ControlTemplate>
"@)
    $b.Template = $template
    $b.Foreground = $(if ($primary) { [Windows.Media.Brushes]::White } else { $brText })
    return $b
}

$btnSave = New-StyledButton '保存' $true
$btnSave.Add_Click({
    $keymap = @{}
    foreach ($k in $boxes.Keys) {
        $keys = @($boxes[$k].Tag.tokens | Where-Object { $_ })
        if ($keys) { $keymap[$k] = @($keys | ForEach-Object { $_.ToLower() }) }
    }
    if (-not (Test-Path $cfgDir)) { New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null }
    @{keymap = $keymap; candPerRow = $script:perRow; japanese_punct = [bool]$punctCb.IsChecked} | ConvertTo-Json -Depth 4 | Set-Content $cfgPath -Encoding UTF8
    $btnSave.Content = '✓ 已保存'
    $btnSave.IsEnabled = $false
    $timer = New-Object Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromSeconds(1.5)
    $timer.Add_Tick({
        param($s, $e)
        $btnSave.Content = '保存'
        $btnSave.IsEnabled = $true
        $s.Stop()
    })
    $timer.Start()
})

$btnReset = New-StyledButton '恢复默认' $false
$btnReset.Add_Click({
    foreach ($k in $boxes.Keys) {
        $boxes[$k].Tag.tokens = @($defaults[$k])
        $boxes[$k].Child.Text = ($defaults[$k] -join '  ')
    }
    $script:perRow = 9
    & $script:updateSeg
    $punctCb.IsChecked = $true
})

$btnCancel = New-StyledButton '取消' $false
$btnCancel.Add_Click({ $win.Close() })

$btnRow.Children.Add($btnReset) | Out-Null
$btnRow.Children.Add($btnCancel) | Out-Null
$btnRow.Children.Add($btnSave) | Out-Null
$stack.Children.Add($btnRow) | Out-Null

[void]$win.ShowDialog()
