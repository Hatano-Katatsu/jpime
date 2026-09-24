# -*- coding: utf-8 -*-
"""罗马字 -> 假名 转换器（无第三方依赖，可独立单测）。

用法:
    conv = RomajiConverter()
    conv.input('k')        # -> 'k'    未完成的音节原样保留
    conv.input('a')        # -> 'か'
    conv.input('n')        # -> 'かn'   n 后面可能跟元音，先挂起
    conv.input('j')        # -> 'かんj' n 后接辅音 -> ん
    conv.input('i')        # -> 'かんじ'
"""

# 统一的罗马字 -> 假名表，长度 1~4，匹配时从长到短。
_TABLE = {
    # 单字母
    'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
    '-': 'ー',
    # 清音
    'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
    'sa': 'さ', 'si': 'し', 'shi': 'し', 'su': 'す', 'se': 'せ', 'so': 'そ',
    'ta': 'た', 'ti': 'ち', 'chi': 'ち', 'tu': 'つ', 'tsu': 'つ', 'te': 'て', 'to': 'と',
    'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
    'ha': 'は', 'hi': 'ひ', 'hu': 'ふ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ',
    'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
    'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
    'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
    'wa': 'わ', 'wo': 'を',
    # 浊音 / 半浊音
    'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
    'za': 'ざ', 'zi': 'じ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ',
    'da': 'だ', 'di': 'ぢ', 'du': 'づ', 'de': 'で', 'do': 'ど',
    'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
    'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
    # 拗音
    'kya': 'きゃ', 'kyi': 'きぃ', 'kyu': 'きゅ', 'kye': 'きぇ', 'kyo': 'きょ',
    'gya': 'ぎゃ', 'gyi': 'ぎぃ', 'gyu': 'ぎゅ', 'gye': 'ぎぇ', 'gyo': 'ぎょ',
    'sha': 'しゃ', 'syi': 'しぃ', 'shu': 'しゅ', 'she': 'しぇ', 'sho': 'しょ',
    'sya': 'しゃ', 'syu': 'しゅ', 'sye': 'しぇ', 'syo': 'しょ',
    'ja': 'じゃ', 'ju': 'じゅ', 'je': 'じぇ', 'jo': 'じょ',
    'zya': 'じゃ', 'zyi': 'じぃ', 'zyu': 'じゅ', 'zye': 'じぇ', 'zyo': 'じょ',
    'jya': 'じゃ', 'jyi': 'じぃ', 'jyu': 'じゅ', 'jye': 'じぇ', 'jyo': 'じょ',
    'cha': 'ちゃ', 'cyi': 'ちぃ', 'chu': 'ちゅ', 'che': 'ちぇ', 'cho': 'ちょ',
    'tya': 'ちゃ', 'tyi': 'ちぃ', 'tyu': 'ちゅ', 'tye': 'ちぇ', 'tyo': 'ちょ',
    'cya': 'ちゃ', 'cyu': 'ちゅ', 'cyo': 'ちょ',
    'tsa': 'つぁ', 'tsi': 'つぃ', 'tse': 'つぇ', 'tso': 'つぉ',
    'tha': 'てゃ', 'thi': 'てぃ', 'thu': 'てゅ', 'the': 'てぇ', 'tho': 'てょ',
    'dha': 'でゃ', 'dhi': 'でぃ', 'dhu': 'でゅ', 'dhe': 'でぇ', 'dho': 'でょ',
    'nya': 'にゃ', 'nyi': 'にぃ', 'nyu': 'にゅ', 'nye': 'にぇ', 'nyo': 'にょ',
    'hya': 'ひゃ', 'hyi': 'ひぃ', 'hyu': 'ひゅ', 'hye': 'ひぇ', 'hyo': 'ひょ',
    'bya': 'びゃ', 'byi': 'びぃ', 'byu': 'びゅ', 'bye': 'びぇ', 'byo': 'びょ',
    'pya': 'ぴゃ', 'pyi': 'ぴぃ', 'pyu': 'ぴゅ', 'pye': 'ぴぇ', 'pyo': 'ぴょ',
    'mya': 'みゃ', 'myi': 'みぃ', 'myu': 'みゅ', 'mye': 'みぇ', 'myo': 'みょ',
    'rya': 'りゃ', 'ryi': 'りぃ', 'ryu': 'りゅ', 'rye': 'りぇ', 'ryo': 'りょ',
    'fa': 'ふぁ', 'fi': 'ふぃ', 'fu': 'ふ', 'fe': 'ふぇ', 'fo': 'ふぉ', 'fyu': 'ふゅ',
    'va': 'ゔぁ', 'vi': 'ゔぃ', 'vu': 'ゔ', 've': 'ゔぇ', 'vo': 'ゔぉ',
    'vya': 'ゔゃ', 'vyu': 'ゔゅ', 'vyo': 'ゔょ',
    'wi': 'うぃ', 'we': 'うぇ',
    'wha': 'うぁ', 'whi': 'うぃ', 'whu': 'う', 'whe': 'うぇ', 'who': 'うぉ',
    # tch 促音惯用写法
    'tcha': 'っちゃ', 'tchi': 'っち', 'tchu': 'っちゅ', 'tche': 'っちぇ', 'tcho': 'っちょ',
    # 小假名（x / l 前缀）
    'xa': 'ぁ', 'xi': 'ぃ', 'xu': 'ぅ', 'xe': 'ぇ', 'xo': 'ぉ',
    'la': 'ぁ', 'li': 'ぃ', 'lu': 'ぅ', 'le': 'ぇ', 'lo': 'ぉ',
    'xtu': 'っ', 'ltu': 'っ', 'xtsu': 'っ', 'ltsu': 'っ',
    'xya': 'ゃ', 'xyi': 'ぃ', 'xyu': 'ゅ', 'xye': 'ぇ', 'xyo': 'ょ',
    'lya': 'ゃ', 'lyi': 'ぃ', 'lyu': 'ゅ', 'lye': 'ぇ', 'lyo': 'ょ',
    'xwa': 'ゎ', 'lwa': 'ゎ', 'xka': 'ヵ', 'xke': 'ヶ', 'lka': 'ヵ', 'lke': 'ヶ',
}

_MAX_LEN = 4

# 可以构成促音（っ）的辅音（n 走拨音规则，单独处理）
_CONSONANTS = frozenset('bcdfghjklmnpqrstvwxyz')


def _match(buf, i):
    """在 buf[i:] 上按 4/3/2/1 最长匹配查表，返回 (假名, 消耗长度) 或 None。"""
    for n in range(min(_MAX_LEN, len(buf) - i), 0, -1):
        kana = _TABLE.get(buf[i:i + n])
        if kana is not None:
            return kana, n
    return None


def to_kana(buf):
    """把罗马字缓冲转成显示字符串：已确定的假名 + 未完成的罗马字尾巴。

    规则要点：
    - 'nn' -> ん；'n' 后接除 y 外的辅音 -> ん；'n' 后接元音/n/y 时挂起等待
    - "n'" -> ん（撇号强制结束拨音）
    - 同一辅音双写 -> 促音 っ（如 kka -> っか）
    - 无法匹配的字符（数字、符号等）原样透传
    """
    out = []
    i = 0
    n = len(buf)
    while i < n:
        ch = buf[i]
        # 1. 先查表（含 na行/nya拗音/nn 等），能成音节就直接出假名
        m = _match(buf, i)
        if m:
            kana, used = m
            out.append(kana)
            i += used
            continue
        # 2. 拨音（'nn' 不在表里，统一在这里处理）：
        #    n+n+元音/y -> ん + な行音节（konnichiha -> こんにちは）
        #    n+n+其它/词尾 -> ん；"n'" -> ん；n+辅音(非y) -> ん；否则挂起
        if ch == 'n':
            nxt = buf[i + 1] if i + 1 < n else ''
            nxt2 = buf[i + 2] if i + 2 < n else ''
            if nxt == "'":
                out.append('ん')
                i += 2
                continue
            if nxt == 'n':
                out.append('ん')
                i += 1 if nxt2 in 'aiueoy' else 2
                continue
            if nxt and nxt in _CONSONANTS and nxt != 'y':
                out.append('ん')
                i += 1
                continue
            out.append('n')
            i += 1
            continue
        # 3. 促音：同一辅音双写 -> っ
        if (ch in _CONSONANTS and i + 1 < n and buf[i + 1] == ch):
            out.append('っ')
            i += 1
            continue
        # 4. 单字符辅音：可能是音节开头，挂起保留原样
        if ch in _CONSONANTS:
            out.append(ch)
            i += 1
            continue
        # 5. 其它字符（数字、符号、撇号等）原样透传
        out.append(ch)
        i += 1
    return ''.join(out)


def kana_for_conversion(buf):
    """供转换引擎使用的假名串：
    尾部挂起的单个 'n' 视为 ん，其余未完成的罗马字尾巴直接去掉。
    """
    s = to_kana(buf)
    stripped = s.rstrip('abcdefghijklmnopqrstuvwxyz')
    tail = s[len(stripped):]
    if tail == 'n':
        return stripped + 'ん'
    return stripped


def hira_to_kata(s):
    """平假名 -> 全角片假名（其它字符不变）。"""
    out = []
    for ch in s:
        code = ord(ch)
        if 0x3041 <= code <= 0x3096:  # ぁ..ゖ
            out.append(chr(code + 0x60))
        else:
            out.append(ch)
    return ''.join(out)


def _build_half_kata_map():
    fw = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ' \
         'マミムメモヤユヨラリルレロワヲンァィゥェォャュョッヮヰヱヴー'
    hw = ['ｱ', 'ｲ', 'ｳ', 'ｴ', 'ｵ', 'ｶ', 'ｷ', 'ｸ', 'ｹ', 'ｺ',
          'ｻ', 'ｼ', 'ｽ', 'ｾ', 'ｿ', 'ﾀ', 'ﾁ', 'ﾂ', 'ﾃ', 'ﾄ',
          'ﾅ', 'ﾆ', 'ﾇ', 'ﾈ', 'ﾉ', 'ﾊ', 'ﾋ', 'ﾌ', 'ﾍ', 'ﾎ',
          'ﾏ', 'ﾐ', 'ﾑ', 'ﾒ', 'ﾓ', 'ﾔ', 'ﾕ', 'ﾖ', 'ﾗ', 'ﾘ',
          'ﾙ', 'ﾚ', 'ﾛ', 'ﾜ', 'ｦ', 'ﾝ', 'ｧ', 'ｨ', 'ｩ', 'ｪ',
          'ｫ', 'ｬ', 'ｭ', 'ｮ', 'ｯ', 'ﾜ', 'ｲ', 'ｴ', 'ｳﾞ', 'ｰ']
    m = dict(zip(fw, hw))
    voiced = 'ガギグゲゴザジズゼゾダヂヅデドバビブベボ'
    bases = 'カキクケコサシスセソタチツテトハヒフヘホ'
    for v, b in zip(voiced, bases):
        m[v] = m[b] + 'ﾞ'
    p_voiced = 'パピプペポ'
    p_bases = 'ハヒフヘホ'
    for v, b in zip(p_voiced, p_bases):
        m[v] = m[b] + 'ﾟ'
    return m


_HALF_KATA_MAP = _build_half_kata_map()


def hira_to_half_kata(s):
    """平假名 -> 半角片假名（浊音拆成 半角+ﾞ/ﾟ，无法映射的字符不变）。"""
    kata = hira_to_kata(s)
    return ''.join(_HALF_KATA_MAP.get(ch, ch) for ch in kata)


class RomajiConverter:
    """维护一个可编辑的罗马字缓冲。"""

    def __init__(self):
        self.buf = []

    def input(self, ch):
        self.buf.append(ch.lower())
        return self.display()

    def backspace(self):
        if self.buf:
            self.buf.pop()
        return self.display()

    def clear(self):
        self.buf = []
        return ''

    def display(self):
        return to_kana(''.join(self.buf))

    def __len__(self):
        return len(self.buf)

    def __bool__(self):
        return bool(self.buf)
