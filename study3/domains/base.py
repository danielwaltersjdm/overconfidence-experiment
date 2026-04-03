"""
Shared Question dataclass used by all domain modules.
"""
from dataclasses import dataclass, field


@dataclass
class Question:
    domain: str          # "stocks", "crypto", "weather", "nba", "forex", "commodities"
    question_id: str     # unique per domain+item+date, e.g. "stocks_AAPL"
    question_text: str   # what the model is asked to predict
    context: str         # information provided to the model
    unit: str            # unit of the answer, e.g. "USD", "°F", "total points"
    current_value: float # reference/current value (for context; 0.0 if N/A)
    target_date: str     # ISO date string when the outcome resolves
    metadata: dict = field(default_factory=dict)  # domain-specific extras

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "question_id": self.question_id,
            "question_text": self.question_text,
            "context": self.context,
            "unit": self.unit,
            "current_value": self.current_value,
            "target_date": self.target_date,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(
            domain=d["domain"],
            question_id=d["question_id"],
            question_text=d["question_text"],
            context=d["context"],
            unit=d["unit"],
            current_value=d["current_value"],
            target_date=d["target_date"],
            metadata=d.get("metadata", {}),
        )
