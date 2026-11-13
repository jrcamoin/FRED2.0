"""Shared immutable data objects passed between FRED's services and adapters."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RiskLevel(StrEnum):
    ROUTINE = "routine"
    CAREGIVER = "caregiver"
    URGENT = "urgent"


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    NEEDS_HELP = "needs_help"
    MISSED = "missed"


@dataclass(frozen=True, slots=True)
class Reminder:
    reminder_id: str
    message: str
    due_at: datetime
    recurrence: str = "none"
    status: ReminderStatus = ReminderStatus.SCHEDULED
    occurrence_at: datetime | None = None
    voice_note_uri: str = ""


@dataclass(frozen=True, slots=True)
class CaregiverContact:
    contact_id: str
    name: str
    channel: str
    destination: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AlertDelivery:
    delivery_id: str
    contact_id: str
    reason: str
    risk: RiskLevel
    status: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    provider_id: str = ""


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
    turn_id: int | None = None


@dataclass(frozen=True, slots=True)
class ResponseFeedback:
    feedback_id: str
    assistant_turn_id: int
    prompt: str
    response: str
    rating: str
    correction: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovedMemory:
    memory_id: str
    content: str
    created_at: datetime


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
