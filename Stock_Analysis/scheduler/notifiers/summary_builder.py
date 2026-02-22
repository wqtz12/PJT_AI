"""
═══════════════════════════════════════════════════════════════
  Summary Builder - 배치 분석 결과 요약 포매터
  텍스트 및 HTML 형식으로 알림용 요약 생성
═══════════════════════════════════════════════════════════════
"""
from datetime import datetime


def _pos_emoji(position: str) -> str:
    """포지션별 이모지"""
    return {"매수": "\U0001f7e2", "매도": "\U0001f534", "홀드": "\U0001f7e1"}.get(position, "\u26aa")


def _pos_emoji_text(position: str) -> str:
    """포지션별 이모지+텍스트"""
    return f"{_pos_emoji(position)}{position}"


def build_batch_summary_text(
    watchlist_name: str,
    results: list,
) -> str:
    """
    텍스트 형식 배치 요약 (텔레그램/슬랙/파일용).

    Format:
    ━━━ BigTech 분석 완료 ━━━
    2026-02-22 09:00 KST | 6종목 (5성공, 1실패)

    종목  | 포지션 | 확신도 | 현재가    | 등락률
    ───────────────────────────────────────
    AAPL  | 매수  | 72%   | $185.50  | +1.2%
    ...

    매크로: 중립 | VIX: 18.5
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    lines = []
    lines.append(f"\u2501\u2501\u2501 {watchlist_name} \ubd84\uc11d \uc644\ub8cc \u2501\u2501\u2501")
    lines.append(f"{now} | {len(results)}\uc885\ubaa9 ({success_count}\uc131\uacf5, {fail_count}\uc2e4\ud328)")
    lines.append("")

    # 헤더
    lines.append(f"{'종목':<8} | {'포지션':^6} | {'확신도':^5} | {'현재가':>10} | {'등락률':>7}")
    lines.append("\u2500" * 52)

    # 종목별 결과
    for r in sorted(results, key=lambda x: x.ticker):
        if r.success:
            pos = _pos_emoji_text(r.dominant_position or "홀드")
            conf = f"{r.avg_confidence:.0f}%"
            price = f"${r.current_price:.2f}" if r.current_price else "N/A"
            change = f"{r.change_pct:+.1f}%" if r.change_pct is not None else "N/A"
        else:
            pos = "\u274c\uc2e4\ud328"
            conf = "\u2014"
            price = "\u2014"
            change = "\u2014"

        lines.append(f"{r.ticker:<8} | {pos:^8} | {conf:>5} | {price:>10} | {change:>7}")

    lines.append("")

    # 매크로 환경 (첫 번째 성공 결과에서)
    macro_env = None
    for r in results:
        if r.success and r.macro_environment:
            macro_env = r.macro_environment
            break
    if macro_env:
        lines.append(f"\ub9e4\ud06c\ub85c \ud658\uacbd: {macro_env}")

    # 종합 포지션 통계
    buy_total = sum(r.buy_count for r in results if r.success)
    sell_total = sum(r.sell_count for r in results if r.success)
    hold_total = sum(r.hold_count for r in results if r.success)
    if buy_total + sell_total + hold_total > 0:
        lines.append(f"\uc885\ud569: \ub9e4\uc218 {buy_total} | \ud640\ub4dc {hold_total} | \ub9e4\ub3c4 {sell_total}")

    return "\n".join(lines)


def build_batch_summary_html(
    watchlist_name: str,
    results: list,
) -> str:
    """HTML 형식 배치 요약 (이메일용)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
  .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  h1 {{ color: #333; font-size: 20px; margin: 0 0 4px; }}
  .subtitle {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: #f8f9fa; padding: 10px 8px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600; }}
  td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
  .buy {{ color: #28a745; font-weight: bold; }}
  .sell {{ color: #dc3545; font-weight: bold; }}
  .hold {{ color: #ffc107; font-weight: bold; }}
  .fail {{ color: #999; }}
  .price {{ text-align: right; font-family: monospace; }}
  .change-pos {{ color: #28a745; }}
  .change-neg {{ color: #dc3545; }}
  .footer {{ margin-top: 20px; padding-top: 12px; border-top: 1px solid #eee; color: #999; font-size: 12px; }}
  .macro {{ background: #f8f9fa; padding: 10px; border-radius: 8px; margin-top: 16px; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">
  <h1>\U0001f4ca {watchlist_name} \ubd84\uc11d \uacb0\uacfc</h1>
  <div class="subtitle">{now} | {len(results)}\uc885\ubaa9 ({success_count}\uc131\uacf5, {fail_count}\uc2e4\ud328)</div>

  <table>
    <thead>
      <tr><th>\uc885\ubaa9</th><th>\ud3ec\uc9c0\uc158</th><th>\ud655\uc2e0\ub3c4</th><th class="price">\ud604\uc7ac\uac00</th><th class="price">\ub4f1\ub77d\ub960</th></tr>
    </thead>
    <tbody>
"""

    for r in sorted(results, key=lambda x: x.ticker):
        if r.success:
            pos_class = {"매수": "buy", "매도": "sell", "홀드": "hold"}.get(
                r.dominant_position or "홀드", "hold")
            pos_text = r.dominant_position or "홀드"
            conf = f"{r.avg_confidence:.0f}%"
            price = f"${r.current_price:.2f}" if r.current_price else "N/A"
            if r.change_pct is not None:
                change_class = "change-pos" if r.change_pct >= 0 else "change-neg"
                change = f"{r.change_pct:+.1f}%"
            else:
                change_class = ""
                change = "N/A"
            html += f"""      <tr>
        <td><strong>{r.ticker}</strong><br><small>{r.name}</small></td>
        <td class="{pos_class}">{pos_text}</td>
        <td>{conf}</td>
        <td class="price">{price}</td>
        <td class="price {change_class}">{change}</td>
      </tr>
"""
        else:
            html += f"""      <tr>
        <td><strong>{r.ticker}</strong></td>
        <td class="fail">\uc2e4\ud328</td>
        <td class="fail">\u2014</td>
        <td class="fail">\u2014</td>
        <td class="fail">\u2014</td>
      </tr>
"""

    # 매크로 환경
    macro_env = None
    for r in results:
        if r.success and r.macro_environment:
            macro_env = r.macro_environment
            break

    html += """    </tbody>
  </table>
"""

    if macro_env:
        html += f"""  <div class="macro">\U0001f30d \ub9e4\ud06c\ub85c \ud658\uacbd: <strong>{macro_env}</strong></div>
"""

    html += """  <div class="footer">
    \u26a0 \ubcf8 \ub9ac\ud3ec\ud2b8\ub294 \uc790\ub3d9 \uc0dd\uc131\ub41c \uae30\uc220\uc801 \ubd84\uc11d \uc790\ub8cc\uc774\uba70, \ud22c\uc790 \ud310\ub2e8\uc758 \ucc38\uace0\uc790\ub8cc\ub85c\ub9cc \ud65c\uc6a9\ud558\uc2dc\uae30 \ubc14\ub78d\ub2c8\ub2e4.
  </div>
</div>
</body>
</html>"""

    return html
