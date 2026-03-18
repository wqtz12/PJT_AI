"""
공통 데이터 모델 - Article, ExpertOpinion, AnalystRating
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    """뉴스 기사 데이터 모델"""
    title: str
    source: str
    url: str
    published: str
    summary: str = ""
    sentiment: str = "neutral"     # positive / negative / neutral
    relevance: float = 0.0         # 0.0 ~ 1.0

    def to_dict(self) -> dict:
        return {
            "제목": self.title,
            "출처": self.source,
            "URL": self.url,
            "발행일": self.published,
            "요약": self.summary,
            "감성": self.sentiment,
            "관련도": self.relevance,
        }


@dataclass
class AnalystRating:
    """개별 애널리스트 등급 데이터"""
    firm: str
    date: str
    grade: str                     # Buy / Hold / Sell / Neutral 등
    from_grade: str = ""
    action: str = ""               # up / down / main / init
    target_price: float = 0.0
    prior_target: float = 0.0

    @property
    def position(self) -> str:
        """등급을 매수/홀드/매도로 정규화"""
        g = self.grade.lower()
        if any(x in g for x in ["buy", "outperform", "overweight", "strong buy"]):
            return "매수"
        elif any(x in g for x in ["sell", "underperform", "underweight", "strong sell"]):
            return "매도"
        else:
            return "홀드"

    @property
    def action_kr(self) -> str:
        mapping = {"up": "⬆ 상향", "down": "⬇ 하향", "main": "➡ 유지", "init": "🆕 신규"}
        return mapping.get(self.action, self.action)

    def to_dict(self) -> dict:
        return {
            "증권사": self.firm,
            "날짜": self.date,
            "등급": self.grade,
            "포지션": self.position,
            "변경": self.action_kr,
            "목표가": f"${self.target_price:.2f}" if self.target_price else "N/A",
            "이전목표가": f"${self.prior_target:.2f}" if self.prior_target else "N/A",
        }


@dataclass
class ExpertOpinion:
    """전문가 분석 의견"""
    expert_name: str               # 전문가 이름/유형
    expert_style: str              # 분석 스타일 설명
    position: str                  # 매수 / 홀드 / 매도
    confidence: float              # 확신도 0~100%
    buy_price: Optional[float] = None    # 매수 목표가
    sell_price: Optional[float] = None   # 매도 목표가
    stop_loss: Optional[float] = None    # 손절가
    rationale: str = ""            # 근거
    key_indicators: list = field(default_factory=list)  # 핵심 참고 지표
    # 3분할 매수/매도가 (일목균형표 기반)
    buy_prices: Optional[list] = field(default=None)    # [1차(보수적), 2차(중간), 3차(적극적)]
    sell_prices: Optional[list] = field(default=None)   # [1차(보수적), 2차(중간), 3차(적극적)]

    @property
    def risk_reward(self) -> Optional[dict]:
        """리스크/리워드 프레이밍 자동 계산 (v2.1)

        매수가, 매도가, 손절가로부터 상방/하방 시나리오와 리스크:리워드 비율을 산출합니다.
        """
        if not self.buy_price or not self.sell_price or not self.stop_loss:
            return None
        if self.buy_price <= 0:
            return None

        upside_pct = (self.sell_price - self.buy_price) / self.buy_price * 100
        downside_pct = (self.buy_price - self.stop_loss) / self.buy_price * 100

        if downside_pct <= 0:
            return None

        rr_ratio = round(upside_pct / downside_pct, 1)

        return {
            "upside_pct": round(upside_pct, 1),
            "downside_pct": round(downside_pct, 1),
            "risk_reward_ratio": rr_ratio,
            "summary": f"상방 +{upside_pct:.1f}% / 하방 -{downside_pct:.1f}% (R:R {rr_ratio}:1)",
        }

    def to_dict(self) -> dict:
        result = {
            "전문가": self.expert_name,
            "스타일": self.expert_style,
            "포지션": self.position,
            "확신도": f"{self.confidence:.0f}%",
            "매수가": f"${self.buy_price:.2f}" if self.buy_price else "—",
            "매도가": f"${self.sell_price:.2f}" if self.sell_price else "—",
            "손절가": f"${self.stop_loss:.2f}" if self.stop_loss else "—",
            "근거": self.rationale,
            "핵심지표": self.key_indicators,
        }
        if self.buy_prices:
            result["3분할_매수"] = [f"${p:.2f}" for p in self.buy_prices]
        if self.sell_prices:
            result["3분할_매도"] = [f"${p:.2f}" for p in self.sell_prices]
        # 리스크/리워드 프레이밍 자동 포함
        rr = self.risk_reward
        if rr:
            result["리스크_리워드"] = rr["summary"]
        return result
