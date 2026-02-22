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


def generate_report(
    ticker: str,
    company_info: dict,
    df: pd.DataFrame,
    signals: dict,
    chart_paths: list,
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
  직원수    : {company_info.get('직원수', 'N/A')}명
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
  배당수익률: {company_info.get('배당수익률', 0) or 0:.2%}
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
  ATR (14일)          : ${latest.get('ATR', 0):.4f}
  ADX (추세강도)       : {latest.get('ADX', 0):.1f}

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

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  8. 생성된 차트 파일
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
