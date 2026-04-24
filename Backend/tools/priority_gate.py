from typing import Dict, Tuple


class PriorityGate:
    """
    Scores action importance from 1..10.
    If score > 7, action should be confirmed by the user.
    """

    HIGH_RISK_TERMS = {
        "bank",
        "payment",
        "money",
        "finance",
        "delete",
        "password",
        "transfer",
        "contract",
        "legal",
        "urgent",
        "مصيري",
        "فلوس",
        "تحويل",
        "حساب",
        "باسورد",
    }

    def score(self, action: Dict) -> Tuple[int, str]:
        text = " ".join(
            [
                str(action.get("platform", "")),
                str(action.get("to", "")),
                str(action.get("message", "")),
                str(action.get("type", "")),
            ]
        ).lower()

        score = 3
        reasons = []

        if action.get("type") in {"video_prep", "zoom_prep"}:
            score += 2
            reasons.append("meeting preparation")
        if len(str(action.get("message", ""))) > 180:
            score += 1
            reasons.append("long message")
        if any(term in text for term in self.HIGH_RISK_TERMS):
            score += 5
            reasons.append("high-risk keywords")
        if action.get("platform") in {"whatsapp", "meta", "telegram"}:
            score += 1
            reasons.append("external social action")

        score = max(1, min(score, 10))
        reason = ", ".join(reasons) if reasons else "normal automation action"
        return score, reason

