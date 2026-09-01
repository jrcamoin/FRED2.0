import json
import os
from datetime import UTC, datetime
from typing import Sequence
from urllib.request import Request, urlopen

from .models import CheckIn, ConversationTurn, RiskLevel
from .ports import CaregiverNotifier, LanguageModel
from .safety import SafetyPolicy
from .storage import SQLiteStore


class OfflineCompanion:
    """Predictable fallback used when no remote language model is configured."""

    def reply(self, history: Sequence[ConversationTurn]) -> str:
        last = history[-1].content.lower()
        if any(word in last for word in ("remember", "memory", "photo")):
            return "We can look at a familiar photo together. What do you notice in it?"
        if any(word in last for word in ("lonely", "sad", "worried")):
            return "I am a robot, but I can listen. Would you like to talk about someone you care about?"
        return "Thank you for telling me. Would you like to tell me a little more?"


class OpenAICompatibleModel:
    """Optional remote model adapter; no audio or conversation is sent unless configured."""

    SYSTEM_PROMPT = """You are the conversation feature of a clearly identified robot companion for a person living with dementia. Be calm, warm, concise, and use one idea or question at a time. Never claim to be human. Never diagnose, provide medication instructions, contradict the person's lived experience aggressively, or promise that help is coming. Do not request secrets or unnecessary personal data. Encourage contact with a trusted person for health, safety, financial, or legal decisions. Reply in no more than 60 words."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", endpoint: str = "https://api.openai.com/v1/chat/completions") -> None:
        self.api_key, self.model, self.endpoint = api_key, model, endpoint

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleModel | None":
        key = os.environ.get("ROBOT_LLM_API_KEY")
        if not key:
            return None
        return cls(key, os.environ.get("ROBOT_LLM_MODEL", "gpt-4.1-mini"), os.environ.get("ROBOT_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions"))

    def reply(self, history: Sequence[ConversationTurn]) -> str:
        payload = json.dumps({"model": self.model, "temperature": 0.4, "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}] + [{"role": turn.role, "content": turn.content} for turn in history]}).encode()
        request = Request(self.endpoint, data=payload, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
        return str(result["choices"][0]["message"]["content"]).strip()


class ConversationService:
    def __init__(self, store: SQLiteStore, model: LanguageModel, notifier: CaregiverNotifier, policy: SafetyPolicy | None = None) -> None:
        self.store, self.model, self.notifier = store, model, notifier
        self.policy = policy or SafetyPolicy()

    def respond(self, text: str, now: datetime | None = None) -> tuple[str, RiskLevel]:
        at = now or datetime.now(UTC)
        assessment = self.policy.assess_conversation(CheckIn(text, at))
        self.store.append_turn(ConversationTurn("user", text.strip(), at))
        if assessment.risk is RiskLevel.URGENT:
            reply = assessment.supportive_message
            self.notifier.notify(assessment)
        else:
            if assessment.risk is RiskLevel.CAREGIVER:
                self.notifier.notify(assessment)
            try:
                reply = self.model.reply(self.store.conversation())
            except Exception:
                reply = OfflineCompanion().reply(self.store.conversation())
        self.store.append_turn(ConversationTurn("assistant", reply, at))
        return reply, assessment.risk
