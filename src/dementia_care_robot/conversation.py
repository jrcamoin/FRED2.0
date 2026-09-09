import json
import os
import re
from datetime import UTC, datetime
from typing import Sequence
from urllib.request import Request, urlopen

from .api_errors import explain_api_error
from .config import offline_mode
from .models import CareProfile, CheckIn, ConversationTurn, RiskLevel
from .ports import CaregiverNotifier, LanguageModel
from .safety import SafetyPolicy
from .storage import SQLiteStore


class OfflineCompanion:
    """Predictable fallback used when no remote language model is configured."""

    def reply(self, history: Sequence[ConversationTurn], profile: CareProfile | None = None) -> str:
        last = history[-1].content.strip().lower()

        missing_items = {
            "keys": (r"\b(key|keys)\b", "by the door, on a nearby table, in your coat or bag, or in the usual basket or bowl"),
            "glasses": (r"\b(glasses|spectacles)\b", "beside your bed or chair, in the bathroom, on a table, or in their usual case"),
            "phone": (r"\b(phone|mobile|cell phone)\b", "beside your chair or bed, on a table, in a pocket or bag, or near its charger"),
            "wallet": (r"\b(wallet|purse)\b", "in your coat or bag, by the door, on a table, or in its usual drawer or basket"),
            "remote": (r"\b(remote|remote control)\b", "beside your chair, between the cushions, on a table, or near the television"),
        }
        looking = re.search(r"\b(find|finding|look(?:ing)? for|lost|left|where(?:'s| is| are))\b", last)
        for item, (pattern, common_places) in missing_items.items():
            if looking and re.search(pattern, last):
                locations = profile.usual_item_locations if profile else ""
                known_place = next((entry.strip() for entry in re.split(r"[;\n.!]", locations) if re.search(pattern, entry.lower())), "")
                if known_place:
                    name = f"{profile.preferred_name}, " if profile.preferred_name else ""
                    return (
                        f"{name}your care profile says: {known_place}. Let's check there first. "
                        f"If the {item} are not there, we can try {common_places}."
                    )
                return (
                    f"Let's look for your {item} together, one place at a time. Start where you last remember using them. "
                    f"Then check {common_places}. If they are still missing, ask your support person to help."
                )

        if profile:
            for pattern, value in (
                (r"\b(routine|schedule)\b", profile.daily_routine),
                (r"\b(hobbies|interests|activities|bored)\b", profile.interests),
                (r"\b(comfort|relax|calm)\b", profile.comforts),
                (r"\b(family|important people)\b", profile.important_people),
            ):
                if re.search(pattern, last):
                    return f"Your care profile says: {value}" if value.strip() else "There is no saved detail about that yet. Your caregiver can add it in the Care Profile below."
        if re.search(r"\bwhat (?:day|date) is it\b", last):
            return f"Today is {datetime.now().astimezone().strftime('%A, %B %-d, %Y')}."
        if re.search(r"\bwhat time is it\b", last):
            return f"It is {datetime.now().astimezone().strftime('%-I:%M %p')}."
        if re.search(r"\b(thirsty|drink|water)\b", last):
            return "If it is safe for you to do so, try checking the kitchen for a glass of water. If you need help getting a drink, ask your support person."
        if re.search(r"\b(hungry|food|something to eat|meal)\b", last):
            return "Let's check your usual meal plan or the kitchen for a familiar ready-to-eat snack. Please ask your support person before cooking if you are unsure."
        if re.search(r"\b(medicine|medication|pill|pills)\b", last):
            return "Please check your labeled medication schedule or dispenser. I cannot tell you what dose to take. If anything is unclear, contact your caregiver or pharmacist before taking it."
        if any(word in last for word in ("remember", "memory", "photo")):
            return "We can look at a familiar photo together. What do you notice in it?"
        if any(word in last for word in ("lonely", "sad", "worried")):
            return "I am a robot, but I can listen. Would you like to talk about someone you care about?"
        return "Thank you for telling me. Would you like to tell me a little more?"


class OpenAICompatibleModel:
    """Optional remote model adapter; no audio or conversation is sent unless configured."""

    SYSTEM_PROMPT = """You are the conversation feature of a clearly identified robot companion for a person living with dementia. Be calm, warm, concise, and use one idea or question at a time. Give useful, concrete, low-risk next steps for everyday questions. For a misplaced item, suggest checking the last-used place and a short list of common locations, one place at a time. Never pretend to know a personal fact or an item's location; clearly describe unverified ideas as suggestions. Never claim to be human. Never diagnose, provide medication instructions, contradict the person's lived experience aggressively, or promise that help is coming. Do not request secrets or unnecessary personal data. Encourage contact with a trusted person for health, safety, financial, or legal decisions. Reply in no more than 60 words."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", endpoint: str = "https://api.openai.com/v1/chat/completions") -> None:
        self.api_key, self.model, self.endpoint = api_key, model, endpoint

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleModel | None":
        if offline_mode():
            return None
        key = os.environ.get("ROBOT_LLM_API_KEY")
        if not key:
            return None
        return cls(key, os.environ.get("ROBOT_LLM_MODEL", "gpt-4.1-mini"), os.environ.get("ROBOT_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions"))

    def reply(self, history: Sequence[ConversationTurn], profile: CareProfile | None = None) -> str:
        profile_text = ""
        if profile:
            details = (
                ("Preferred name", profile.preferred_name), ("Important people", profile.important_people),
                ("Interests", profile.interests), ("Daily routine", profile.daily_routine),
                ("Comforting things", profile.comforts), ("Usual item locations", profile.usual_item_locations),
            )
            provided = [f"- {label}: {value}" for label, value in details if value.strip()]
            if provided:
                profile_text = "\nCaregiver-provided care profile (use only when relevant; do not invent missing details):\n" + "\n".join(provided)
        payload = json.dumps({"model": self.model, "temperature": 0.4, "messages": [{"role": "system", "content": self.SYSTEM_PROMPT + profile_text}] + [{"role": turn.role, "content": turn.content} for turn in history]}).encode()
        request = Request(self.endpoint, data=payload, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=20) as response:
                result = json.load(response)
            return str(result["choices"][0]["message"]["content"]).strip()
        except Exception as error:
            raise explain_api_error(error, "Conversation") from error


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
            reply = self.model.reply(self.store.conversation(), self.store.care_profile())
        self.store.append_turn(ConversationTurn("assistant", reply, at))
        return reply, assessment.risk
