from typing import Protocol, Sequence

from .models import Assessment, ConversationTurn, FamiliarMedia


class Speaker(Protocol):
    def say(self, message: str) -> None: ...


class CaregiverNotifier(Protocol):
    def notify(self, assessment: Assessment) -> None: ...


class MediaDisplay(Protocol):
    def show(self, media: FamiliarMedia) -> None: ...


class LanguageModel(Protocol):
    def reply(self, history: Sequence[ConversationTurn]) -> str: ...
