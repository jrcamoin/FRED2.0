from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RiskLevel(StrEnum):
    ROUTINE = "routine"
    CAREGIVER = "caregiver"
    URGENT = "urgent"


@dataclass(frozen=True, slots=True)
class Reminder:
    reminder_id: str
    message: str
    due_at: datetime


@dataclass(frozen=True, slots=True)
class FamiliarMedia:
    media_id: str
    title: str
    uri: str
    kind: str = "image"
    description: str = ""


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str
    at: datetime


@dataclass(frozen=True, slots=True)
class CareProfile:
    preferred_name: str = ""
    important_people: str = ""
    interests: str = ""
    daily_routine: str = ""
    comforts: str = ""
    usual_item_locations: str = ""


@dataclass(frozen=True, slots=True)
class CheckIn:
    response: str | None
    at: datetime


@dataclass(frozen=True, slots=True)
class Assessment:
    risk: RiskLevel
    reason: str
    supportive_message: str
