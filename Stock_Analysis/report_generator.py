"""
분석 리포트 생성 모듈 - 텍스트 기반 종합 분석 보고서
"""
import pandas as pd
import numpy as np
from datetime import datetime


def format_number(num):
    """숫자를 읽기 쉬운 형태로 변환"""
    if isinstance(num, str) or num == "N/A":
        return str(num)
    if num is None:
        return "N/A"
    if abs(num) >= 1e12:
        return f"${num/1e12:.2f}T"
    elif abs(num) >= 1e9:
        return f"${num/1e9:.2f}B"
    elif abs(num) >= 1e6:
        return f"${num/1e6:.2f}M"
    elif abs(num) >= 1e3:
        return f"${num/1e3:.1f}K"
    else:
        return f"${num:.2f}" if isinstance(num, float) else str(num)


def _safe_dividend_yield(val) -> str:
    """배당수익률을 안전하게 포맷 (yfinance 값 범위 보정)"""
    if val is None or val == 0:
        return "0.00%"
    v = float(val)
    # yfinance가 이미 퍼센트로 반환하는 경우 (0.27 = 0.27% 의미)
    # 실제 20% 이상 배당수익률은 극히 드묾
    if v > 0.20:
        return f"{v:.2f}%"
    # 일반적 비율 (0.0027 → 0.27%)
    return f"{v:.2%}"


def _format_split_prices(prices: list) -> str:
    """3분할 가격 리스트를 슬래시 구분 문자열로 변환"""
    if not prices:
        return "—"
    return " / ".join(str(p) for p in prices)


def _build_expert_section(experts_data: dict) -> str:
    """전문가 분석 결과를 텍스트 표로 구성"""
    experts = experts_data.get("experts", [])
    aggregated = experts_data.get("aggregated", {})
    filters = experts_data.get("filters_applied", [])

    section = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  8. 5전문가 종합 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # 8-1. 전문가별 상세 분석
    for i, exp in enumerate(experts, 1):
        name = exp.get("전문가", f"전문가 {i}")
        position = exp.get("포지션", "—")
        confidence = exp.get("확신도", "—")
        buy_price = exp.get("매수가", "—")
        sell_price = exp.get("매도가", "—")
        stop_loss = exp.get("손절가", "—")
        rationale = exp.get("근거", "")
        rr = exp.get("리스크_리워드", "")

        pos_icon = {"매수": "🟢", "매도": "🔴", "홀드": "🟡"}.get(position, "⚪")

        section += f"""
  ┌─ [{i}] {name} ─────────────────────────────
  │  포지션: {pos_icon} {position}  |  확신도: {confidence}
  │  매수가: {buy_price}  |  매도가: {sell_price}  |  손절가: {stop_loss}
  │  근거: {rationale}
"""
        if rr:
            section += f"  │  리스크/리워드: {rr}\n"
        section += "  └──────────────────────────────────────────────\n"

    # 8-2. 3분할 매수/매도 가격표 (포지션 무관, 항상 표시)
    section += """
  ┌─ 3분할 매수/매도 가격표 (일목균형표 기반) ────────────
  │
  │  포지션과 무관하게 모든 전문가의 분할 진입/청산 가격입니다.
  │  1차(보수적) → 2차(중간) → 3차(적극적) 순서
  │
"""
    # 테이블 헤더
    section += "  │  {:<14s} {:^6s} {:^6s} {:^22s} {:^22s}\n".format(
        "전문가", "포지션", "확신도", "3분할 매수", "3분할 매도"
    )
    section += "  │  {}\n".format("─" * 74)

    for exp in experts:
        name = exp.get("전문가", "—")
        # 이름을 짧게 축약
        short_name = name.replace(" 전문가", "").replace(" 트레이더", "")
        position = exp.get("포지션", "—")
        confidence = exp.get("확신도", "—")
        split_buy = _format_split_prices(exp.get("3분할_매수"))
        split_sell = _format_split_prices(exp.get("3분할_매도"))

        section += "  │  {:<14s} {:^6s} {:>6s} {:^22s} {:^22s}\n".format(
            short_name, position, confidence, split_buy, split_sell
        )

    section += "  │\n  └──────────────────────────────────────────────\n"

    # 8-3. 가중 집계 결과
    dominant = aggregated.get("dominant", "—")
    w_buy = aggregated.get("weighted_buy", 0)
    w_sell = aggregated.get("weighted_sell", 0)
    w_hold = aggregated.get("weighted_hold", 0)
    total_w = aggregated.get("total_weight", 0)
    cycle = aggregated.get("market_cycle", {})
    conflicts = aggregated.get("opinion_conflicts", [])

    dom_icon = {"매수": "🟢", "매도": "🔴", "홀드": "🟡"}.get(dominant, "⚪")

    section += f"""
  ┌─────────────────────────────────────────────┐
  │  >>> 전문가 종합 판정: {dom_icon} {dominant:6s}               │
  │      매수 {w_buy:.1f} / 홀드 {w_hold:.1f} / 매도 {w_sell:.1f}  (총 {total_w:.1f})  │
  └─────────────────────────────────────────────┘
"""

    if cycle:
        phase = cycle.get("phase", "—")
        score = cycle.get("score", 0)
        reasons = cycle.get("reasons", [])
        section += f"  시장 사이클: {phase} (점수: {score})\n"
        for r in reasons:
            section += f"    - {r}\n"

    if conflicts:
        section += "\n  전문가 충돌 패턴:\n"
        for c in conflicts:
            section += f"    ⚡ {c}\n"

    if filters:
        section += "\n  의견 필터 적용:\n"
        for f in filters:
            section += f"    🔄 {f}\n"

    return section


def generate_report(
    ticker: str,
    company_info: dict,
    df: pd.DataFrame,
    signals: dict,
    chart_paths: list,
    experts_data: dict = None,
) -> str:
    """종합 분석 리포트 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    price = latest["Close"]
    change = price - prev["Close"]
    change_pct = (change / prev["Close"]) * 100

    # 기간별 수익률
    returns = {}
    for days, label in [(5, "1주"), (20, "1개월"), (60, "3개월"), (120, "6개월"), (252, "1년")]:
        if len(df) > days:
            past_price = df.iloc[-days - 1]["Close"]
            ret = ((price - past_price) / past_price) * 100
            returns[label] = ret

    # 변동성
    daily_returns = df["Close"].pct_change().dropna()
    volatility_20d = daily_returns.tail(20).std() * np.sqrt(252) * 100
    volatility_60d = daily_returns.tail(60).std() * np.sqrt(252) * 100

    # 52주 범위 내 위치
    high_52w = company_info.get("52주_최고", 0)
    low_52w = company_info.get("52주_최저", 0)
    range_pct = ((price - low_52w) / (high_52w - low_52w) * 100) if high_52w != low_52w else 0

    report = f"""
{'='*70}
  {company_info.get('이름', ticker)} ({ticker}) 종합 분석 리포트
  생성일시: {now}
{'='*70}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. 기업 개요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  종목명    : {company_info.get('이름', 'N/A')}
  섹터      : {company_info.get('섹터', 'N/A')}
  산업      : {company_info.get('산업', 'N/A')}
  시가총액  : {format_number(company_info.get('시가총액', 0))}
  직원수    : {f"{int(company_info['직원수']):,}명" if company_info.get('직원수') else 'N/A'}
  홈페이지  : {company_info.get('홈페이지', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2. 현재 주가 현황
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  현재가    : ${price:.2f}
  전일대비  : {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)
  52주 최고 : ${high_52w:.2f}
  52주 최저 : ${low_52w:.2f}
  52주 범위 위치: {range_pct:.1f}% (0%=최저, 100%=최고)
  거래량    : {latest['Volume']:,.0f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  3. 기간별 수익률
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    for label, ret in returns.items():
        arrow = "▲" if ret >= 0 else "▼"
        report += f"  {label:8s}: {arrow} {'+' if ret >= 0 else ''}{ret:.2f}%\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  4. 투자 지표
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  PER       : {company_info.get('PER', 'N/A')}
  PBR       : {company_info.get('PBR', 'N/A')}
  EPS       : {company_info.get('EPS', 'N/A')}
  배당수익률: {_safe_dividend_yield(company_info.get('배당수익률', 0))}
  베타      : {company_info.get('베타', 'N/A')}
  총매출    : {format_number(company_info.get('총매출', 0))}
  영업이익  : {format_number(company_info.get('영업이익', 0))}
  부채비율  : {company_info.get('부채비율', 'N/A')}
  보유현금  : {format_number(company_info.get('현금', 0))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  5. 기술적 분석 (매매 신호)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    for indicator, val in signals.items():
        if indicator == "종합판단":
            continue
        if isinstance(val, tuple) and len(val) == 2:
            value, interpretation = val
            report += f"  {indicator:12s}: {value:20s} → {interpretation}\n"
        else:
            report += f"  {indicator:12s}: {str(val)}\n"

    report += f"""
  ┌─────────────────────────────────────────────┐
  │  >>> 종합 판단: {signals.get('종합판단', 'N/A'):30s} │
  └─────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  6. 변동성 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  20일 변동성 (연율화): {volatility_20d:.1f}%
  60일 변동성 (연율화): {volatility_60d:.1f}%
  ATR (14일)          : ${latest.get('ATR') or 0:.4f}
  ADX (추세강도)       : {latest.get('ADX') or 0:.1f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  7. 애널리스트 전망
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  목표 주가  : ${company_info.get('애널리스트_목표가', 'N/A')}
  추천 의견  : {company_info.get('추천', 'N/A')}
"""

    target = company_info.get("애널리스트_목표가")
    if target and target != "N/A":
        upside = ((float(target) - price) / price) * 100
        report += f"  상승 여력  : {'+' if upside >= 0 else ''}{upside:.1f}%\n"

    # 8. 전문가 종합 분석 (experts_data가 있을 때만)
    if experts_data and experts_data.get("experts"):
        report += _build_expert_section(experts_data)

    # 9. 생성된 차트 파일 (차트가 있을 때만)
    if chart_paths:
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  9. 생성된 차트 파일
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for i, path in enumerate(chart_paths, 1):
            report += f"  [{i}] {path}\n"

    report += f"""
{'='*70}
  ⚠ 본 리포트는 자동 생성된 기술적 분석 자료이며,
    투자 판단의 참고자료로만 활용하시기 바랍니다.
    투자에 대한 최종 결정과 책임은 투자자 본인에게 있습니다.
{'='*70}
"""
    return report
