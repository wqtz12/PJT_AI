"""
시각화 모듈 - 기술적 분석 차트 생성
- 크로스 플랫폼 한글 폰트 자동 감지 (macOS / Windows / Linux)
- 차트 설정은 config.yaml에서 로드
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import mplfinance as mpf
import os
import sys
import logging

from common.config import get_config

logger = logging.getLogger(__name__)

# ─── config.yaml에서 차트 설정 로드 ───
_cfg = get_config()
_chart_cfg = _cfg.get("chart", {})
_DPI = _chart_cfg.get("dpi", 150)
_CANDLE_FIGSIZE = tuple(_chart_cfg.get("candlestick_figsize", [16, 10]))
_DASHBOARD_FIGSIZE = tuple(_chart_cfg.get("dashboard_figsize", [16, 20]))
_PERFORMANCE_FIGSIZE = tuple(_chart_cfg.get("performance_figsize", [14, 10]))
_SMA_COLORS = _chart_cfg.get("sma_colors", {
    "SMA_5": "#FF6B6B", "SMA_20": "#4ECDC4", "SMA_60": "#45B7D1", "SMA_120": "#96CEB4"
})
_CANDLE_UP = _chart_cfg.get("candle_up", "red")
_CANDLE_DOWN = _chart_cfg.get("candle_down", "blue")


# ─── 크로스 플랫폼 한글 폰트 자동 감지 ───
import matplotlib.font_manager as fm


def _find_korean_font() -> str:
    """
    OS별 한글 폰트 자동 탐색

    탐색 순서:
    1. macOS: AppleGothic → Apple SD Gothic Neo
    2. Windows: Malgun Gothic → NanumGothic → Gulim
    3. Linux: NanumGothic → NanumBarunGothic → UnDotum → Noto Sans CJK KR
    4. 시스템 설치 폰트 중 한글 지원 폰트 탐색
    5. 폴백: sans-serif (한글 깨질 수 있음)

    Returns:
        str: 사용할 폰트 이름
    """
    platform = sys.platform

    # OS별 후보 폰트 경로 + 이름
    if platform == "darwin":  # macOS
        candidates = [
            ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", None),
            ("/System/Library/Fonts/AppleSDGothicNeo.ttc", None),
            ("/Library/Fonts/NanumGothic.ttf", None),
            ("/Library/Fonts/NanumGothic.otf", None),
        ]
    elif platform == "win32":  # Windows
        windir = os.environ.get("WINDIR", "C:\\Windows")
        fonts_dir = os.path.join(windir, "Fonts")
        candidates = [
            (os.path.join(fonts_dir, "malgun.ttf"), None),
            (os.path.join(fonts_dir, "NanumGothic.ttf"), None),
            (os.path.join(fonts_dir, "gulim.ttc"), None),
            (os.path.join(fonts_dir, "batang.ttc"), None),
        ]
    else:  # Linux
        candidates = [
            ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", None),
            ("/usr/share/fonts/nanum/NanumGothic.ttf", None),
            ("/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf", None),
            ("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf", None),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", None),
            ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", None),
        ]

    # 1단계: 파일 경로 기반 탐색
    for font_path, _ in candidates:
        if os.path.exists(font_path):
            try:
                fm.fontManager.addfont(font_path)
                prop = fm.FontProperties(fname=font_path)
                font_name = prop.get_name()
                logger.info(f"한글 폰트 발견 (경로): {font_name} ({font_path})")
                return font_name
            except Exception as e:
                logger.debug(f"폰트 로드 실패: {font_path} - {e}")
                continue

    # 2단계: matplotlib 등록 폰트 중 한글 폰트 탐색
    korean_keywords = [
        "Gothic", "Nanum", "Gulim", "Batang", "Dotum", "Malgun",
        "Apple SD", "AppleGothic", "Noto Sans CJK", "Noto Sans KR",
        "맑은", "나눔", "굴림", "바탕", "돋움",
    ]
    all_fonts = {f.name for f in fm.fontManager.ttflist}
    for keyword in korean_keywords:
        matched = [name for name in all_fonts if keyword.lower() in name.lower()]
        if matched:
            font_name = sorted(matched)[0]  # 일관성 위해 정렬
            logger.info(f"한글 폰트 발견 (등록): {font_name}")
            return font_name

    # 3단계: 폴백
    logger.warning("한글 폰트를 찾지 못했습니다. sans-serif로 폴백합니다. (한글이 깨질 수 있음)")
    logger.warning("해결: NanumGothic 설치 → pip install fonts-nanum 또는 sudo apt install fonts-nanum")
    return "sans-serif"


# 폰트 설정 적용
_font_name = _find_korean_font()
plt.rcParams["font.family"] = _font_name
plt.rcParams["axes.unicode_minus"] = False

# mplfinance용 rc 설정
_mpf_rc = {"font.family": _font_name, "axes.unicode_minus": False}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def get_current_font() -> str:
    """현재 사용 중인 폰트 이름 반환 (디버깅용)"""
    return _font_name


def plot_candlestick_with_indicators(df: pd.DataFrame, ticker: str, company_name: str) -> str:
    """캔들스틱 + 이동평균 + 거래량 차트"""
    df_plot = df.copy()
    df_plot.index = pd.DatetimeIndex(df_plot.index)

    add_plots = []

    # 이동평균선 (config에서 색상 로드)
    for col, color in _SMA_COLORS.items():
        if col in df_plot.columns:
            add_plots.append(mpf.make_addplot(df_plot[col], color=color, width=1.0, label=col))

    # 볼린저밴드
    if "BB_Upper" in df_plot.columns:
        add_plots.append(mpf.make_addplot(df_plot["BB_Upper"], color="gray", linestyle="--", width=0.7))
        add_plots.append(mpf.make_addplot(df_plot["BB_Lower"], color="gray", linestyle="--", width=0.7))

    filepath = os.path.join(OUTPUT_DIR, f"{ticker}_candlestick.png")

    mc = mpf.make_marketcolors(up=_CANDLE_UP, down=_CANDLE_DOWN, edge="inherit", wick="inherit", volume="in")
    style = mpf.make_mpf_style(marketcolors=mc, gridstyle="-", gridcolor="#E8E8E8", rc=_mpf_rc)

    fig, axes = mpf.plot(
        df_plot,
        type="candle",
        style=style,
        volume=True,
        addplot=add_plots if add_plots else None,
        title=f"\n{company_name} ({ticker}) - 캔들스틱 차트",
        figsize=_CANDLE_FIGSIZE,
        returnfig=True,
    )

    fig.savefig(filepath, dpi=_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return filepath


def plot_technical_dashboard(df: pd.DataFrame, ticker: str, company_name: str) -> str:
    """기술적 분석 대시보드 (RSI, MACD, 스토캐스틱, OBV)"""
    fig = plt.figure(figsize=_DASHBOARD_FIGSIZE)
    gs = GridSpec(5, 1, height_ratios=[3, 1.2, 1.2, 1.2, 1.2], hspace=0.3)

    dates = df.index

    # 1) 주가 + 볼린저밴드
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(dates, df["Close"], color="#2196F3", linewidth=1.5, label="종가")
    if "BB_Upper" in df.columns:
        ax1.fill_between(dates, df["BB_Upper"], df["BB_Lower"], alpha=0.1, color="gray", label="볼린저밴드")
        ax1.plot(dates, df["BB_Upper"], color="gray", linewidth=0.7, linestyle="--")
        ax1.plot(dates, df["BB_Lower"], color="gray", linewidth=0.7, linestyle="--")
    for col, color, lbl in [("SMA_20", "#FF9800", "SMA20"), ("SMA_60", "#9C27B0", "SMA60")]:
        if col in df.columns:
            ax1.plot(dates, df[col], color=color, linewidth=1.0, label=lbl, alpha=0.8)
    ax1.set_title(f"{company_name} ({ticker}) - 기술적 분석 대시보드", fontsize=14, fontweight="bold")
    ax1.set_ylabel("주가 ($)")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 2) RSI
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    if "RSI" in df.columns:
        ax2.plot(dates, df["RSI"], color="#E91E63", linewidth=1.2)
        ax2.axhline(y=70, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.axhline(y=30, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.axhline(y=50, color="gray", linestyle=":", alpha=0.3, linewidth=0.8)
        ax2.fill_between(dates, 30, df["RSI"], where=(df["RSI"] < 30), alpha=0.2, color="green")
        ax2.fill_between(dates, 70, df["RSI"], where=(df["RSI"] > 70), alpha=0.2, color="red")
    ax2.set_ylabel("RSI")
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)

    # 3) MACD
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    if "MACD" in df.columns:
        ax3.plot(dates, df["MACD"], color="#2196F3", linewidth=1.2, label="MACD")
        ax3.plot(dates, df["MACD_Signal"], color="#FF9800", linewidth=1.0, label="Signal")
        hist = df["MACD_Hist"]
        colors = ["#4CAF50" if v >= 0 else "#F44336" for v in hist]
        ax3.bar(dates, hist, color=colors, alpha=0.6, width=1.5)
        ax3.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
    ax3.set_ylabel("MACD")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(True, alpha=0.3)

    # 4) 스토캐스틱
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    if "Stoch_K" in df.columns:
        ax4.plot(dates, df["Stoch_K"], color="#2196F3", linewidth=1.2, label="%K")
        ax4.plot(dates, df["Stoch_D"], color="#FF9800", linewidth=1.0, label="%D")
        ax4.axhline(y=80, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax4.axhline(y=20, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
    ax4.set_ylabel("Stochastic")
    ax4.set_ylim(0, 100)
    ax4.legend(loc="upper left", fontsize=8)
    ax4.grid(True, alpha=0.3)

    # 5) OBV
    ax5 = fig.add_subplot(gs[4], sharex=ax1)
    if "OBV" in df.columns:
        ax5.plot(dates, df["OBV"], color="#607D8B", linewidth=1.2)
        ax5.fill_between(dates, df["OBV"], alpha=0.1, color="#607D8B")
    ax5.set_ylabel("OBV")
    ax5.set_xlabel("날짜")
    ax5.grid(True, alpha=0.3)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    filepath = os.path.join(OUTPUT_DIR, f"{ticker}_technical_dashboard.png")
    fig.savefig(filepath, dpi=_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return filepath


def plot_performance_summary(df: pd.DataFrame, ticker: str, company_name: str) -> str:
    """수익률 및 변동성 요약 차트"""
    fig, axes = plt.subplots(2, 2, figsize=_PERFORMANCE_FIGSIZE)
    fig.suptitle(f"{company_name} ({ticker}) - 수익률/변동성 분석", fontsize=14, fontweight="bold")

    # 1) 일간 수익률 분포
    returns = df["Close"].pct_change().dropna()
    axes[0, 0].hist(returns, bins=50, color="#2196F3", alpha=0.7, edgecolor="white")
    axes[0, 0].axvline(returns.mean(), color="red", linestyle="--", label=f"평균: {returns.mean():.4f}")
    axes[0, 0].set_title("일간 수익률 분포")
    axes[0, 0].set_xlabel("수익률")
    axes[0, 0].set_ylabel("빈도")
    axes[0, 0].legend()

    # 2) 누적 수익률
    cum_returns = (1 + returns).cumprod() - 1
    axes[0, 1].plot(cum_returns.index, cum_returns.values, color="#4CAF50", linewidth=1.5)
    axes[0, 1].fill_between(cum_returns.index, cum_returns.values, alpha=0.1, color="#4CAF50")
    axes[0, 1].axhline(y=0, color="gray", linestyle="-", alpha=0.5)
    axes[0, 1].set_title("누적 수익률")
    axes[0, 1].set_ylabel("수익률")
    axes[0, 1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 3) 거래량 추이
    axes[1, 0].bar(df.index, df["Volume"], color="#FF9800", alpha=0.6, width=1.5)
    vol_ma = df["Volume"].rolling(window=20).mean()
    axes[1, 0].plot(df.index, vol_ma, color="red", linewidth=1.2, label="20일 평균")
    axes[1, 0].set_title("거래량 추이")
    axes[1, 0].set_ylabel("거래량")
    axes[1, 0].legend()
    axes[1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 4) 20일 롤링 변동성
    rolling_vol = returns.rolling(window=20).std() * np.sqrt(252)
    axes[1, 1].plot(rolling_vol.index, rolling_vol.values, color="#E91E63", linewidth=1.2)
    axes[1, 1].fill_between(rolling_vol.index, rolling_vol.values, alpha=0.1, color="#E91E63")
    axes[1, 1].set_title("20일 롤링 변동성 (연율화)")
    axes[1, 1].set_ylabel("변동성")
    axes[1, 1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    for ax in axes.flat:
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    filepath = os.path.join(OUTPUT_DIR, f"{ticker}_performance.png")
    fig.savefig(filepath, dpi=_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return filepath
