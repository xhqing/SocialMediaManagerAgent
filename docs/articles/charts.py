#!/usr/bin/env python3
"""生成复利系列文章（《怎么证明一个方法真的不亏》《押多少、做多少次》）的全部附图，并复核文中全部数字。

运行：python3 docs/articles/charts.py
输出：docs/articles/img/*.png

图中数据口径：
- 全部为公开示例参数的演算 / 示意模拟，不是任何实盘记录；
- 示例策略：胜率 55%、赢 +1.5R、亏 -1R，即 EV = +0.375R、E[R^2] = 1.6875。
"""

from __future__ import annotations

import math
import pathlib

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.sans-serif"] = [
    "Hiragino Sans GB",
    "Heiti TC",
    "Songti SC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.dpi"] = 200
matplotlib.rcParams["savefig.bbox"] = "tight"

# 统一深色主题：背景纯黑，线条与文字用浅色（2026-11-07 用户立规）
matplotlib.style.use("dark_background")
matplotlib.rcParams.update({
    "figure.facecolor": "black",
    "axes.facecolor": "black",
    "savefig.facecolor": "black",
    "axes.edgecolor": "#D1D5DB",
    "axes.labelcolor": "#F3F4F6",
    "text.color": "#F3F4F6",
    "xtick.color": "#D1D5DB",
    "ytick.color": "#D1D5DB",
    "grid.color": "#4B5563",
    "savefig.pad_inches": 0.28,
})

OUT = pathlib.Path(__file__).parent / "img"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 示例参数（二结果模型）
P, RW, RL = 0.55, 1.5, 1.0          # 胜率 / 赢时赔率 / 亏时幅度
Q = 1 - P
EV = P * RW - Q * RL                # +0.375
ER2 = P * RW**2 + Q * RL**2         # 1.6875
SIGMA = math.sqrt(ER2 - EV**2)      # ≈1.2437


def g_exact(f: float) -> float:
    """真实每笔对数增长率 g(f) = E[ln(1+fR)]（两结果精确解）。"""
    if f >= 1 / RL:
        return float("nan")
    return P * math.log(1 + f * RW) + Q * math.log(1 - f * RL)


def g_naive(f: float) -> float:
    """错误算法隐含的增长率：ln(1+f·EV)，永远向上。"""
    return math.log(1 + f * EV)


# 深色背景配色：线条与文字要亮，深色系在纯黑上不可读
C_BLUE, C_DARK, C_GREEN = "#60A5FA", "#E5E7EB", "#34D399"
C_RED, C_ORANGE, C_GRAY = "#F87171", "#FBBF24", "#9CA3AF"

# 图 1：样本不够时，什么曲线都像有优势 -------------------------------------------------

def fig_sample_noise() -> None:
    n_max = 300
    ns = np.arange(1, n_max + 1)
    band = 2 * SIGMA / np.sqrt(ns)

    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    ax.fill_between(ns, EV - band, EV + band, color=C_BLUE, alpha=0.15,
                    label="理论范围：EV ± 2 个标准误", linewidth=0)
    ax.axhline(0, color=C_RED, linestyle="-.", linewidth=1.2)

    rng = np.random.default_rng(20261013)   # 固定随机种子，可复现
    for i in range(6):
        r = np.where(rng.random(n_max) < P, RW, -RL)
        run = np.cumsum(r) / ns
        ax.plot(ns, run, color=C_GRAY, linewidth=0.9, alpha=0.8,
                label="六条随机样本路径" if i == 0 else None)

    ax.axhline(EV, color=C_DARK, linewidth=1.4, label=f"真实期望 EV = +{EV:.3f}R")
    n45 = 45
    ax.annotate(f"n≈{n45} 笔之后\n范围才离开 0 线",
                xy=(n45, EV - 2 * SIGMA / math.sqrt(n45)),
                xytext=(95, -0.55), fontsize=9, color=C_RED,
                arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.0))
    ax.set_xlim(1, n_max)
    ax.set_ylim(-1.5, 2.0)
    ax.set_xlabel("已经做了多少笔（n）")
    ax.set_ylabel("样本均值（R）")
    ax.set_title("样本不够时，“平均为正”可能只是噪声", fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
    fig.savefig(OUT / "sample-noise-dark.png")
    plt.close(fig)


# 图 2：去掉最好的 k 笔之后 -------------------------------------------------------------

def fig_trimmed_mean() -> None:
    wins, losses = 9, 16                       # 示意样本：25 笔，9 赢（+3R）、16 亏（-1R）
    arr = sorted([3.0] * wins + [-1.0] * losses, reverse=True)
    ks = list(range(0, 7))
    means = [float(np.mean(arr[k:])) for k in ks]

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    colors = [C_BLUE if m > 0 else C_RED for m in means]
    bars = ax.bar(ks, means, color=colors, width=0.62)
    for k, m, b in zip(ks, means, bars):
        ax.text(k, m + (0.03 if m >= 0 else -0.06), f"{m:+.2f}",
                ha="center", va="bottom" if m >= 0 else "top", fontsize=9)
    ax.axhline(0, color="#9CA3AF", linewidth=1.0)
    ax.set_xticks(ks)
    ax.set_xticklabels([f"去掉最好\n的 {k} 笔" if k else "原样本\n（25 笔）" for k in ks], fontsize=9)
    ax.set_ylim(-0.45, 0.55)
    ax.set_ylabel("剩余样本的平均每笔盈亏（R）")
    ax.set_title("同一个“正期望”样本：去掉最好的 4 笔就转负", fontsize=12)
    ax.grid(axis="y", alpha=0.25)
    fig.savefig(OUT / "trimmed-mean-dark.png")
    plt.close(fig)


# 图 3：g(f) 真实曲线 vs 错误算法（核心图） --------------------------------------------

def fig_growth_curve() -> None:
    fs = np.linspace(0.001, 0.8, 400)
    gs = np.array([g_exact(f) for f in fs])
    naive = np.array([g_naive(f) for f in fs])

    # 精确临界点：g(f)=0 的解（二分法，精度 1e-9）
    lo, hi = 0.001, 1 / RL - 1e-9
    for _ in range(200):
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if g_exact(mid) > 0 else (lo, mid)
    f_crit = (lo + hi) / 2

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.axhline(0, color="#9CA3AF", linewidth=1.0)
    ax.axvspan(f_crit, 0.8, color=C_RED, alpha=0.07, linewidth=0)
    ax.plot(fs, gs, color=C_BLUE, linewidth=2.2, label="真实增长率 g(f)")
    ax.plot(fs, naive, color=C_RED, linewidth=1.4, linestyle="--",
            label="错误算法隐含的增长率 ln(1+f·EV)")

    ax.plot([0.25], [g_exact(0.25)], "o", color=C_DARK, markersize=6)
    bbox = dict(facecolor="#0B1220", edgecolor="none", alpha=0.85)
    ax.annotate(f"最优 f* = 25%\ng = +{g_exact(0.25)*100:.2f}%/笔",
                xy=(0.25, g_exact(0.25)), xytext=(0.28, 0.12), fontsize=9, color=C_DARK,
                bbox=bbox, arrowprops=dict(arrowstyle="->", color=C_DARK, lw=1.0))
    ax.plot([f_crit], [0], "o", color=C_RED, markersize=6)
    ax.annotate(f"临界点 ≈ {f_crit*100:.1f}%\n过线即缩水",
                xy=(f_crit, 0), xytext=(0.55, -0.065), fontsize=9, color=C_RED,
                bbox=bbox, arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.0))
    ax.annotate("越激进，错误算法显示得越快",
                xy=(0.70, g_naive(0.70)), xytext=(0.42, 0.15), fontsize=9, color=C_RED,
                bbox=bbox, arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.0))

    ax.set_xlim(0, 0.8)
    ax.set_ylim(-0.10, 0.24)
    ax.set_xlabel("每笔投入的比例 f")
    ax.set_ylabel("每笔的对数增长率 g")
    ax.set_title("同一条方法：下注比例过了临界点，赚钱变亏钱", fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=9, loc="upper left")
    fig.savefig(OUT / "growth-curve-dark.png")
    plt.close(fig)


# 图 4：不同下注比例下的资金曲线（50 笔） ----------------------------------------------

def fig_equity_curves() -> None:
    bets = np.arange(0, 51)
    rows = [(0.02, C_GRAY), (0.10, C_GREEN), (0.25, C_DARK), (0.50, C_ORANGE), (0.60, C_RED)]

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.9), gridspec_kw={"wspace": 0.32})
    for f, c in rows:
        curve = np.exp(bets * g_exact(f))
        lab = f"f = {f*100:.0f}%  → ×{curve[-1]:.2f}"
        axes[0].plot(bets, curve, color=c, linewidth=2.0 if f in (0.25, 0.60) else 1.4, label=lab)
        axes[1].plot(bets, curve, color=c, linewidth=2.0 if f in (0.25, 0.60) else 1.4, label=lab)

    axes[0].axhline(1, color="#9CA3AF", linewidth=0.8, linestyle=":")
    axes[0].set_ylim(0, 10.5)
    axes[0].set_title("看倍数：最优比例跑到 9.8 倍", fontsize=11)
    axes[0].set_ylabel("账户倍数 Wn/W0")

    axes[1].set_yscale("log")
    axes[1].set_ylim(0.03, 20)
    axes[1].set_yticks([0.05, 0.1, 0.5, 1, 5, 10])
    axes[1].set_yticklabels(["0.05", "0.1", "0.5", "1", "5", "10"])
    axes[1].set_title("换对数坐标：向下也是一条直线", fontsize=11)
    axes[1].set_ylabel("账户倍数（对数刻度）")

    for ax in axes:
        ax.set_xlabel("笔数")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, loc="upper left" if ax is axes[0] else "lower left", framealpha=0.9)
    fig.suptitle("同一套方法、只改下注比例：50 笔之后的五种命运", fontsize=12, y=1.02)
    fig.savefig(OUT / "equity-curves-dark.png")
    plt.close(fig)


# 图 5：重复次数的乘法效应 + 频率是双向放大器 -------------------------------------------

def fig_repeat_effect() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.9), gridspec_kw={"wspace": 0.32})

    ns = np.arange(0, 101)
    for gg, c in [(0.01, C_GRAY), (0.03, C_BLUE), (0.05, C_DARK)]:
        axes[0].plot(ns, np.exp(ns * gg), color=c, linewidth=1.8, label=f"g = {gg*100:.0f}% / 笔")
    axes[0].set_yscale("log")
    axes[0].set_ylim(0.9, 200)
    axes[0].annotate("g = 3%：\n5 笔 ×1.16\n50 笔 ×4.48", xy=(50, math.exp(1.5)),
                     xytext=(62, 1.8), fontsize=9, color=C_BLUE,
                     bbox=dict(facecolor="#0B1220", edgecolor="none", alpha=0.85),
                     arrowprops=dict(arrowstyle="->", color=C_BLUE, lw=1.0))
    axes[0].set_title("每多做一次，就多乘一次", fontsize=11)
    axes[0].set_xlabel("笔数 n")
    axes[0].set_ylabel("账户倍数（对数刻度）")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=9, loc="upper left")

    nus = [5, 50, 250]
    x = np.arange(len(nus))
    w = 0.36
    pos = [math.exp(nu * 0.03) for nu in nus]
    neg = [math.exp(nu * -0.03) for nu in nus]
    axes[1].bar(x - w / 2, pos, width=w, color=C_BLUE, label="每笔 g = +3%（有效）")
    axes[1].bar(x + w / 2, neg, width=w, color=C_RED, label="每笔 g = -3%（无效）")
    for xi, v in zip(x - w / 2, pos):
        axes[1].text(xi, v * 1.15, f"{v:.2f}" if v < 100 else f"{v:.0f}", ha="center", fontsize=9)
    for xi, v in zip(x + w / 2, neg):
        axes[1].text(xi, v * 1.25, f"{v:.3g}", ha="center", fontsize=9)
    axes[1].set_yscale("log")
    axes[1].set_ylim(1e-4, 1e5)
    ticks = [1e-4, 1e-3, 1e-2, 1e-1, 1, 1e1, 1e2, 1e3, 1e4]
    axes[1].set_yticks(ticks)
    axes[1].set_yticklabels(["0.0001", "0.001", "0.01", "0.1", "1", "10", "100", "1000", "10000"])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"每年 {nu} 笔" for nu in nus], fontsize=9)
    axes[1].set_title("同一频率，正负两个方向（一年后）", fontsize=11)
    axes[1].set_ylabel("账户倍数（对数刻度）")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(fontsize=8, loc="upper left")
    fig.suptitle("重复次数是放大器：把有效的放大，也把无效的放大", fontsize=12, y=1.02)
    fig.savefig(OUT / "repeat-effect-dark.png")
    plt.close(fig)


def fig_t_distribution() -> None:
    """图 6：$H_0$ 下的 t 分布——观测到的 t 落在哪、p 值多大。"""
    from scipy import stats

    n = 45
    df = n - 1
    t_obs = EV / math.sqrt(SIGMA**2 / n)          # ≈2.02
    p_two = 2 * (1 - stats.t.cdf(t_obs, df))      # ≈0.049

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.9), gridspec_kw={"wspace": 0.3})

    # 左：H0 下的分布 + 观测值 + 双侧尾巴
    ax = axes[0]
    x = np.linspace(-4.5, 4.5, 900)
    y = stats.t.pdf(x, df)
    ax.plot(x, y, color=C_BLUE, lw=2)
    ax.fill_between(x[x >= t_obs], y[x >= t_obs], color=C_RED, alpha=0.3,
                    label=f"两侧尾巴合计 p ≈ {p_two:.3f}")
    ax.fill_between(x[x <= -t_obs], y[x <= -t_obs], color=C_RED, alpha=0.3)
    ax.axvline(t_obs, color=C_RED, ls="--", lw=1.4)
    ax.annotate(f"观测到 t ≈ {t_obs:.2f}",
                xy=(t_obs, 0.03), xytext=(2.9, 0.26),
                arrowprops=dict(arrowstyle="->", color=C_RED),
                color=C_RED, fontsize=9)
    ax.set_title(f"$H_0$（没有优势）成立时，t 会围着 0 随机波动（n={n}）", fontsize=10)
    ax.set_xlabel("t 值")
    ax.set_ylabel("概率密度")
    ax.set_ylim(0, 0.50)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.text(-4.3, 0.22,
            "t 越大，落在尾巴里的概率（p）越小，\n也就越不像运气", fontsize=8.5, va="top")

    # 右：不同自由度的尾巴厚度
    ax = axes[1]
    ax.plot(x, stats.t.pdf(x, 9), color=C_ORANGE, lw=1.8, label="n=10（df=9）")
    ax.plot(x, stats.t.pdf(x, 44), color=C_BLUE, lw=1.8, label="n=45（df=44）")
    ax.plot(x, stats.norm.pdf(x), color=C_GRAY, lw=1.6, ls="--", label="正态（n 很大）")
    ax.axvline(t_obs, color=C_RED, ls=":", lw=1.2)
    ax.set_title("样本越少尾巴越厚：同样的 t 更难算显著", fontsize=10)
    ax.set_xlabel("t 值")
    ax.set_ylabel("概率密度")
    ax.set_ylim(0, 0.50)
    ax.legend(frameon=False, fontsize=9)

    fig.savefig(OUT / "t-distribution-dark.png")
    plt.close(fig)


# ---------------------------------------------------------------- 数字复核
def check_numbers() -> None:
    print(f"EV = {EV:+.4f}   E[R²] = {ER2:.4f}   σ = {SIGMA:.4f}")
    fstar = P / RL - Q / RW
    print(f"精确凯利 f* = {fstar:.4f}   近似 f* = EV/E[R²] = {EV/ER2:.4f}   2f* = {2*fstar:.4f}")
    print(f"精确临界点 f_c = 0.4901（本脚本图 3 数值求解同值）")
    print(f"t=2 所需样本：n ≈ 4σ²/EV² = {4*SIGMA**2/EV**2:.1f} 笔")
    from scipy import stats
    t_obs = EV / math.sqrt(SIGMA**2 / 45)
    print(f"图 6：n=45 时 t = {t_obs:.3f}，双侧 p = {2*(1-stats.t.cdf(t_obs, 44)):.4f}；"
          f"n=10 时 p = {2*(1-stats.t.cdf(t_obs, 9)):.4f}；正态近似 p = {2*(1-stats.norm.cdf(t_obs)):.4f}")
    print(f"{'f':>6}{'真实g/笔':>12}{'50笔真实':>12}{'50笔错误公式':>14}")
    for f in (0.02, 0.10, 0.25, 0.40, 0.50, 0.60):
        print(f"{f*100:>5.0f}%{g_exact(f)*100:>11.3f}%{'×%.4f' % math.exp(50*g_exact(f)):>12}"
              f"{'×%.0f' % (1+f*EV)**50:>14}")
    print(f"g=3% 时：5 笔 ×{math.exp(0.15):.2f}、50 笔 ×{math.exp(1.5):.2f}；"
          f"每年 250 笔一年后 ×{math.exp(7.5):.0f}，反向 ×{math.exp(-7.5):.5f}")


if __name__ == "__main__":
    fig_sample_noise()
    fig_trimmed_mean()
    fig_growth_curve()
    fig_equity_curves()
    fig_repeat_effect()
    fig_t_distribution()
    check_numbers()
    print("\n图已生成 →", OUT)
