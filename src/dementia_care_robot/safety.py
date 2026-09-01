import re

from .models import Assessment, CheckIn, RiskLevel


class SafetyPolicy:
    """Conservative rules only; this is not a diagnostic model."""

    _urgent = re.compile(
        r"\b(fell|fall|chest pain|can't breathe|cannot breathe|bleeding|fire|help me)\b",
        re.IGNORECASE,
    )
    _caregiver = re.compile(
        r"\b(confused|lost|scared|dizzy|unwell|pain|don't know where|do not know where)\b",
        re.IGNORECASE,
    )
    _routine = re.compile(r"\b(ok|okay|fine|good|yes|all right|alright)\b", re.IGNORECASE)

    def assess(self, check_in: CheckIn) -> Assessment:
        response = (check_in.response or "").strip()
        if self._urgent.search(response):
            return Assessment(
                RiskLevel.URGENT,
                "The response may indicate immediate danger.",
                "I heard that you may need urgent help. I am contacting your configured support person now. If you can, use your emergency call device.",
            )
        if not response:
            return Assessment(
                RiskLevel.CAREGIVER,
                "No understandable response was received.",
                "I did not understand. I will let your support person know so they can check in.",
            )
        if self._caregiver.search(response):
            return Assessment(
                RiskLevel.CAREGIVER,
                "The response may indicate distress or disorientation.",
                "Thank you for telling me. I will ask your support person to check in.",
            )
        if self._routine.search(response):
            return Assessment(RiskLevel.ROUTINE, "The person reported they are okay.", "Thank you. I am here if you need another reminder.")
        return Assessment(
            RiskLevel.CAREGIVER,
            "The response was uncertain and needs human review.",
            "Thank you. I am not sure I understood, so I will ask your support person to check in.",
        )

    def assess_conversation(self, check_in: CheckIn) -> Assessment:
        """Screen free conversation without treating every open-ended answer as a missed check-in."""
        response = (check_in.response or "").strip()
        if self._urgent.search(response) or self._caregiver.search(response):
            return self.assess(check_in)
        return Assessment(RiskLevel.ROUTINE, "No explicit safety concern detected.", "")
