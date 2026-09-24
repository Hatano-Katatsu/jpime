// jpime tray companion: tray icon + modern rounded popup menu.
// Style matches the jpime candidate window (white bg, #E0E0E0 border,
// #E5E5E5 hover, #1B1B1B text, #6D6D6D secondary, 8px radius).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class Program {
    private const string PimeDir = @"C:\Program Files (x86)\PIME";
    private const string ModuleDir = PimeDir + @"\python\input_methods\jpime";
    private static readonly string ConfigPath =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                     @"jpime\config.json");

    [STAThread]
    private static void Main() {
        Application.EnableVisualStyles();
        Application.Run(new TrayApp());
    }

    private sealed class TrayApp : ApplicationContext {
        private readonly NotifyIcon _tray;
        private PopupMenu _menu;

        // 读当前候选窗排列（9=横排，1=竖排）
        internal static int GetCandPerRow() {
            try {
                if (File.Exists(ConfigPath)) {
                    var json = File.ReadAllText(ConfigPath);
                    var dict = new JavaScriptSerializer()
                        .Deserialize<Dictionary<string, object>>(json);
                    if (dict != null && dict.ContainsKey("candPerRow"))
                        return Convert.ToInt32(dict["candPerRow"]);
                }
            } catch { }
            return 9;
        }

        internal static void ToggleLayout() {
            int cur = GetCandPerRow();
            int next = cur <= 1 ? 9 : 1;
            try {
                Dictionary<string, object> dict = null;
                if (File.Exists(ConfigPath)) {
                    try {
                        dict = new JavaScriptSerializer()
                            .Deserialize<Dictionary<string, object>>(
                                File.ReadAllText(ConfigPath));
                    } catch { }
                }
                if (dict == null) dict = new Dictionary<string, object>();
                dict["candPerRow"] = next;
                Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath));
                File.WriteAllText(ConfigPath,
                    new JavaScriptSerializer().Serialize(dict),
                    new System.Text.UTF8Encoding(false));  // 无 BOM，Python json 才能读
            } catch (Exception ex) {
                MessageBox.Show("切换失败：" + ex.Message, "日文输入法",
                                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        public TrayApp() {
            _tray = new NotifyIcon {
                Text = "日文输入法（中文式选词）",
                Visible = true
            };
            string iconPath = Path.Combine(ModuleDir, "icon.ico");
            _tray.Icon = File.Exists(iconPath) ? new Icon(iconPath) : SystemIcons.Application;
            _tray.MouseClick += (s, e) => {
                if (e.Button == MouseButtons.Left) OpenSettings();
                else if (e.Button == MouseButtons.Right) ShowMenu();
            };
        }

        protected override void ExitThreadCore() {
            _tray.Visible = false;
            _tray.Dispose();
            base.ExitThreadCore();
        }

        private void ShowMenu() {
            if (_menu != null && !_menu.IsDisposed) { _menu.Close(); }
            _menu = new PopupMenu();
            _menu.ActionSelected += a => {
                switch (a) {
                    case "settings": OpenSettings(); break;
                    case "layout": ToggleLayout(); break;
                    case "config":
                        if (!File.Exists(ConfigPath))
                            Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath));
                        Process.Start("notepad.exe", ConfigPath);
                        break;
                    case "restart": RestartBackend(); break;
                    case "logs":
                        Process.Start("explorer.exe",
                            Path.Combine(Environment.GetFolderPath(
                                Environment.SpecialFolder.LocalApplicationData), @"PIME\Log"));
                        break;
                    case "quit": ExitThread(); break;
                }
            };
            _menu.ShowAtCursor();
        }

        private static void OpenSettings() {
            var psi = new ProcessStartInfo {
                FileName = "powershell.exe",
                Arguments = "-STA -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" +
                            Path.Combine(ModuleDir, "settings.ps1") + "\"",
                CreateNoWindow = true,
                UseShellExecute = false
            };
            Process.Start(psi);
        }

        private static void RestartBackend() {
            string launcher = Path.Combine(PimeDir, "PIMELauncher.exe");
            try {
                Process.Start(new ProcessStartInfo {
                    FileName = launcher, Arguments = "/quit",
                    CreateNoWindow = true, UseShellExecute = false
                }).WaitForExit(3000);
                System.Threading.Thread.Sleep(1500);
                Process.Start(new ProcessStartInfo {
                    FileName = launcher, CreateNoWindow = true, UseShellExecute = false
                });
            } catch (Exception ex) {
                MessageBox.Show("重启失败：" + ex.Message, "日文输入法",
                                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
    }

    // ---- modern rounded popup menu ----
    private sealed class PopupMenu : Form {
        public event Action<string> ActionSelected;

        private sealed class Item {
            public string Id;       // null => separator
            public string Text;
            public string IconFile; // optional ico in ModuleDir
        }

        private static readonly Color Bg = Color.White;
        private static readonly Color Border = Color.FromArgb(0xE0, 0xE0, 0xE0);
        private static readonly Color Txt = Color.FromArgb(0x1B, 0x1B, 0x1B);
        private static readonly Color Hover = Color.FromArgb(0xE5, 0xE5, 0xE5);
        private static readonly Color Sep = Color.FromArgb(0xE0, 0xE0, 0xE0);
        private const int Radius = 8;
        private const int ItemH = 32;
        private const int SepH = 9;
        private const int PadV = 6;
        private const int PadH = 6;
        private const int IconSize = 16;

        private List<Item> BuildItems() {
            string layoutText = TrayApp.GetCandPerRow() <= 1
                ? "切换为横排候选窗 (&H)" : "切换为竖排候选窗 (&V)";
            return new List<Item> {
                new Item { Id = "settings", Text = "打开设置 (&S)",      IconFile = "icon_config.ico" },
                new Item { Id = "layout",   Text = layoutText },
                new Item { Id = "config",   Text = "编辑配置文件 (&E)" },
                new Item { Id = null },
                new Item { Id = "restart",  Text = "重启输入法后端 (&R)" },
                new Item { Id = "logs",     Text = "打开日志目录 (&L)" },
                new Item { Id = null },
                new Item { Id = "quit",     Text = "关闭此托盘图标 (&Q)" },
            };
        }

        private readonly List<Item> _items;
        private readonly Dictionary<string, Image> _icons = new Dictionary<string, Image>();
        private int _hover = -1;
        private int _width = 220;
        private readonly Font _font = new Font("Microsoft YaHei UI", 9f);

        public PopupMenu() {
            _items = BuildItems();
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            TopMost = true;
            StartPosition = FormStartPosition.Manual;
            BackColor = Bg;
            Font = _font;
            using (var g = CreateGraphics()) {
                foreach (var it in _items) {
                    if (it.Id == null) continue;
                    int w = (int)g.MeasureString(it.Text, _font).Width + PadH * 2 + 12 + IconSize + 8;
                    _width = Math.Max(_width, w);
                }
            }
            int h = PadV * 2;
            foreach (var it in _items) h += it.Id == null ? SepH : ItemH;
            ClientSize = new Size(_width, h);
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer
                     | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            // rounded corners
            var path = RoundedRect(new Rectangle(0, 0, _width, h), Radius);
            Region = new Region(path);
            LoadIcons();
        }

        private void LoadIcons() {
            foreach (var it in _items) {
                if (it.IconFile == null || _icons.ContainsKey(it.IconFile)) continue;
                string p = Path.Combine(
                    @"C:\Program Files (x86)\PIME\python\input_methods\jpime", it.IconFile);
                if (File.Exists(p)) {
                    using (var ico = new Icon(p, IconSize, IconSize))
                        _icons[it.IconFile] = ico.ToBitmap();
                }
            }
        }

        private static GraphicsPath RoundedRect(Rectangle r, int rad) {
            var p = new GraphicsPath();
            int d = rad * 2;
            p.AddArc(r.Left, r.Top, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Top, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.Left, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        public void ShowAtCursor() {
            var pos = Cursor.Position;
            var screen = Screen.FromPoint(pos).WorkingArea;
            Location = new Point(
                Math.Min(pos.X, screen.Right - Width - 4),
                Math.Max(screen.Top + 4,
                         pos.Y - Height > screen.Top ? pos.Y - Height : pos.Y));
            Show();
            Activate();
        }

        private int ItemAt(int y) {
            int cur = PadV;
            for (int i = 0; i < _items.Count; i++) {
                int h = _items[i].Id == null ? SepH : ItemH;
                if (y >= cur && y < cur + h) return _items[i].Id == null ? -1 : i;
                cur += h;
            }
            return -1;
        }

        protected override void OnPaint(PaintEventArgs e) {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Bg);
            int y = PadV;
            for (int i = 0; i < _items.Count; i++) {
                var it = _items[i];
                if (it.Id == null) {
                    using (var pen = new Pen(Sep))
                        g.DrawLine(pen, PadH + 4, y + SepH / 2, _width - PadH - 4, y + SepH / 2);
                    y += SepH;
                    continue;
                }
                if (i == _hover) {
                    using (var brush = new SolidBrush(Hover))
                    using (var path = RoundedRect(
                        new Rectangle(PadH, y + 1, _width - PadH * 2, ItemH - 2), 6))
                        g.FillPath(brush, path);
                }
                int tx = PadH + 10;
                if (it.IconFile != null && _icons.ContainsKey(it.IconFile)) {
                    g.DrawImage(_icons[it.IconFile], tx, y + (ItemH - IconSize) / 2, IconSize, IconSize);
                    tx += IconSize + 8;
                }
                TextRenderer.DrawText(g, it.Text, _font, new Point(tx, y + (ItemH - 18) / 2 + 1), Txt,
                    TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix);
                y += ItemH;
            }
            using (var pen = new Pen(Border))
            using (var path = RoundedRect(new Rectangle(0, 0, _width - 1, Height - 1), Radius))
                g.DrawPath(pen, path);
        }

        protected override void OnMouseMove(MouseEventArgs e) {
            int idx = ItemAt(e.Y);
            if (idx != _hover) { _hover = idx; Invalidate(); }
            base.OnMouseMove(e);
        }

        protected override void OnMouseLeave(EventArgs e) {
            _hover = -1; Invalidate();
            base.OnMouseLeave(e);
        }

        protected override void OnMouseClick(MouseEventArgs e) {
            int idx = ItemAt(e.Y);
            if (idx >= 0) {
                string id = _items[idx].Id;
                Close();
                var handler = ActionSelected;
                if (handler != null) handler(id);
            }
            base.OnMouseClick(e);
        }

        protected override void OnKeyDown(KeyEventArgs e) {
            if (e.KeyCode == Keys.Escape) Close();
            else if (e.KeyCode == Keys.Enter && _hover >= 0) {
                string id = _items[_hover].Id; Close();
                var handler = ActionSelected;
                if (handler != null) handler(id);
            } else if (e.KeyCode == Keys.Down || e.KeyCode == Keys.Up) {
                int step = e.KeyCode == Keys.Down ? 1 : -1;
                int i = _hover;
                for (int n = 0; n < _items.Count; n++) {
                    i = (i + step + _items.Count) % _items.Count;
                    if (_items[i].Id != null) break;
                }
                _hover = i; Invalidate();
            }
            base.OnKeyDown(e);
        }

        protected override void OnDeactivate(EventArgs e) {
            Close();
            base.OnDeactivate(e);
        }

        protected override void Dispose(bool disposing) {
            if (disposing) {
                foreach (var img in _icons.Values) img.Dispose();
                _font.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
