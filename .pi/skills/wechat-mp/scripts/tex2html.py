#!/usr/bin/env python3
"""把「简单」的 LaTeX 公式转成 HTML 文本（变量、上下标、希腊字母、四则运算等）。

为什么需要：公众号正文有 2 万字符上限，一篇文章上百个内联公式若全用图片，
光是 <img> 标签就把额度吃光；而简单符号（R、EV、σ²、e^{ng}）用文字表达更自然，
也方便读者选中复制。复杂公式（分式叠套、underbrace、xrightarrow 等）仍走图片。

用法：
    from tex2html import to_text, ComplexMath
    html = to_text(r"\\mathrm{EV}=\\mathbb{E}[R]>0")   # → '<span ...>EV = 𝔼[R] &gt; 0</span>'
    # 抛 ComplexMath 表示「这个公式转不了文字，请用图片」
"""

from __future__ import annotations

import re


class ComplexMath(Exception):
    """该公式不适合转成文本，调用方应改用图片渲染。"""


# 不支持转文本的结构（必须走图片）
FORBIDDEN = re.compile(
    r"\\underbrace|\\overbrace|\\xrightarrow|\\begin|\\end|\\stackrel|\\substack|"
    r"\\overset|\\underset|\\limits|\\\\|\\displaystyle|\\!\\!|\\tag"
)

GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε",
    r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ", r"\kappa": "κ", r"\lambda": "λ",
    r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ",
    r"\tau": "τ", r"\phi": "φ", r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ", r"\Pi": "Π",
    r"\Sigma": "Σ", r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
}

SYMBOLS = {
    r"\times": "×", r"\cdot": "·", r"\div": "÷", r"\pm": "±", r"\mp": "∓",
    r"\approx": "≈", r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
    r"\neq": "≠", r"\equiv": "≡", r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔", r"\ll": "≪", r"\gg": "≫",
    r"\infty": "∞", r"\infty": "∞", r"\sqrt": "√", r"\sim": "∼", r"\propto": "∝",
    r"\in": "∈", r"\subset": "⊂", r"\cup": "∪", r"\cap": "∩", r"\forall": "∀",
    r"\exists": "∃", r"\partial": "∂", r"\nabla": "∇", r"\sum": "∑", r"\prod": "∏",
    r"\bar": "", r"\,": "", r"\;": "", r"\:": "", r"\!": "", r"\ ": " ",
    r"\lvert": "|", r"\rvert": "|", r"\mid": "|", r"\|": "‖",
    r"\%": "%", r"\&": "&", r"\#": "#", r"\$": "$", r"\_": "_", r"\{": "{", r"\}": "}",
    r"\left": "", r"\right": "", r"\big": "", r"\Big": "", r"\bigg": "", r"\Bigg": "",
}

MATHBB = {"E": "𝔼", "R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "P": "ℙ"}
FUNC_CMDS = {r"\ln": "ln", r"\log": "log", r"\exp": "exp", r"\max": "max", r"\min": "min",
             r"\lim": "lim", r"\sup": "sup", r"\inf": "inf", r"\det": "det", r"\gcd": "gcd",
             r"\sin": "sin", r"\cos": "cos", r"\tan": "tan", r"\operatorname{Var}": "Var"}


def _group(s: str, i: int) -> tuple[str, int]:
    """从 s[i] 起取一个组：{...} 或单个字符。返回 (组内容, 下一个位置)。"""
    if i >= len(s):
        raise ComplexMath("公式在此处结束")
    if s[i] == "{":
        depth = 0
        for j in range(i, len(s)):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
        raise ComplexMath("花括号不配对")
    return s[i], i + 1


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _needs_paren(inner: str) -> bool:
    return bool(re.search(r"[+\-×·/]|\\pm|\\mp", inner))


def to_text(tex: str, wrap: bool = True) -> str:
    """LaTeX → HTML 文本。抛 ComplexMath 表示转不了。"""
    if FORBIDDEN.search(tex):
        raise ComplexMath("含不支持转文本的命令")

    s = tex.strip()
    frac_re = re.compile(r"\\(?:d|t)?frac\s*")
    frac_seen = bool(frac_re.search(s))

    # \frac / \dfrac / \tfrac → (A)/(B) 或 A/B
    while True:
        m = frac_re.search(s)
        if not m:
            break
        a, i = _group(s, m.end())
        b, i = _group(s, i)
        a, b = to_text(a, wrap=False), to_text(b, wrap=False)
        num = f"({a})" if _needs_paren(a) else a
        den = f"({b})" if _needs_paren(b) else b
        s = s[:m.start()] + f"{num}/{den}" + s[i:]

    # \sqrt{A} → √(A)
    while True:
        m = re.search(r"\\sqrt\s*", s)
        if not m:
            break
        a, i = _group(s, m.end())
        inner = to_text(a, wrap=False)
        s = s[:m.start()] + (f"√({inner})" if _needs_paren(inner) or len(inner) > 1 else f"√{inner}") + s[i:]

    # \text{...} / \mathrm{...} / \operatorname{...} / \mathbb{X}
    for cmd, kind in ((r"\text", "text"), (r"\mathrm", "text"), (r"\operatorname", "text"),
                      (r"\mathbf", "text"), (r"\mathit", "text"), (r"\mathsf", "text"),
                      (r"\mathbb", "bb"), (r"\mathcal", "text")):
        while True:
            m = re.search(re.escape(cmd) + r"\s*", s)
            if not m:
                break
            a, i = _group(s, m.end())
            inner = to_text(a, wrap=False)
            if kind == "bb":
                inner = "".join(MATHBB.get(ch, ch) for ch in inner)
            s = s[:m.start()] + inner + s[i:]

    # \bar{X} / \hat{X} / \vec{X} → 组合字符
    for cmd, comb in ((r"\bar", "\u0304"), (r"\hat", "\u0302"), (r"\vec", "\u20d7"),
                      (r"\tilde", "\u0303"), (r"\dot", "\u0307")):
        while True:
            m = re.search(re.escape(cmd) + r"\s*", s)
            if not m:
                break
            a, i = _group(s, m.end())
            inner = to_text(a, wrap=False)
            s = s[:m.start()] + (inner[0] + comb + inner[1:] if inner else "") + s[i:]

    # 上下标
    for mark, tag in (("_", "sub"), ("^", "sup")):
        while True:
            pos = None
            for m in re.finditer(re.escape(mark), s):
                if m.start() > 0 and s[m.start() - 1] == "\\":
                    continue
                pos = m
                break
            if not pos:
                break
            a, i = _group(s, pos.end())
            inner = to_text(a, wrap=False)
            # 单字符上标可用 Unicode（² ³ ᵀ 等），更好看
            uni = {"2": "²", "3": "³", "1": "¹", "0": "⁰", "n": "ⁿ", "T": "ᵀ"}
            if tag == "sup" and inner in uni:
                s = s[:pos.start()] + uni[inner] + s[i:]
            else:
                s = s[:pos.start()] + f"<{tag}>{inner}</{tag}>" + s[i:]

    # 简单命令替换（对以字母结尾的命令加字母边界守卫，避免误改前缀；纯符号命令不加）
    for cmd in sorted(list(GREEK) + list(SYMBOLS) + list(FUNC_CMDS), key=len, reverse=True):
        rep = GREEK.get(cmd, SYMBOLS.get(cmd, FUNC_CMDS.get(cmd, "")))
        guard = r"(?![a-zA-Z])" if cmd[-1].isalpha() else ""
        s = re.sub(re.escape(cmd) + guard, rep, s)

    # 剩余未知命令 → 交给图片
    unknown = re.search(r"\\[a-zA-Z]+", s)
    if unknown:
        raise ComplexMath(f"存在未映射的命令：{unknown.group(0)}")

    s = s.replace("\\", "")
    s = re.sub(r"\s{2,}", " ", s).strip()
    if not s:
        raise ComplexMath("空公式")
    limit = 24 if frac_seen else 46  # 含分式的内联公式只在很短时才走文本
    if len(s) > limit:  # 过长的内联公式用图片更好排版
        raise ComplexMath("内联公式过长")
    if wrap:
        # 用 <i> 而不是带 font-family 的 span：每处省上百字符，公众号有 2 万字符上限
        return f"<i>{s}</i>" if re.search(r"[A-Za-zα-ωΑ-Ω]", s) else s
    return s


if __name__ == "__main__":
    tests = [r"\mathrm{EV}=\mathbb{E}[R]>0", r"W_n/W_0", r"e^{ng}", r"\sigma^2",
             r"f^*=0.55-0.45/1.5=25\%", r"\frac{W_n}{W_0}\approx e^{ng}", r"|R_L|=0.5",
             r"\bar R_n\to \mathrm{EV}", r"\mathbb{E}[\ln(1+fR)]", r"4\sigma^2/\mathrm{EV}^2",
             r"g=\mathbb{E}[\ln(1+fR)]", r"f<\dfrac{2\,\mathrm{EV}}{\mathbb{E}[R^2]}",
             r"\underbrace{f\cdot \mathrm{EV}}_{x}"]
    for t in tests:
        try:
            print(f"{t:58s} → {to_text(t)}")
        except ComplexMath as e:
            print(f"{t:58s} → [图片] {e}")
