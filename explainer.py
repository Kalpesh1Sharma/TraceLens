"""Provider-neutral explanations for TraceLens failure issues."""

import json
import logging
import os
from typing import Any, Protocol

from schemas import TraceIssue


logger = logging.getLogger(__name__)


class Explainer(Protocol):
    """Turns one detected trace issue into a developer-facing explanation."""

    def explain(self, issue: TraceIssue) -> str:
        """Return a concise, evidence-grounded explanation and next action."""


class RuleBasedExplainer:
    """Offline explanation provider used when no API key is configured."""

    def explain(self, issue: TraceIssue) -> str:
        if issue.issue_type == "retry_loop":
            return (
                f"{issue.explanation} Review the retry condition for step "
                f"'{issue.step_id}' and stop or change the request after the retry limit."
            )
        if issue.issue_type == "tool_call_error":
            return (
                f"Step '{issue.step_id}' is a tool call with an error status. "
                "Review the recorded tool output, then correct the request or handle "
                "that error before continuing the run."
            )
        if issue.issue_type == "silent_timeout":
            return (
                f"{issue.explanation} Inspect the operation and its timeout limit, and "
                "make sure the timeout path returns an explicit error or result."
            )
        return f"{issue.explanation} Review the recorded event data for step '{issue.step_id}'."


class GroqExplainer:
    """Groq-backed implementation of the provider-neutral ``Explainer`` interface."""

    model = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str, fallback: Explainer | None = None) -> None:
        # Keep this import lazy: offline fallback works even before dependencies
        # have been installed in a local development environment.
        from groq import Groq

        self.client = Groq(api_key=api_key)
        self.fallback = fallback or RuleBasedExplainer()

    def explain(self, issue: TraceIssue) -> str:
        context = json.dumps(
            {
                "step_id": issue.step_id,
                "issue_type": issue.issue_type,
                "detector_explanation": issue.explanation,
                "events": [event.model_dump(mode="json") for event in issue.events],
            },
            separators=(",", ":"),
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_completion_tokens=180,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Explain an observed TraceLens failure for a developer. "
                            "Use only the supplied JSON facts. Do not infer an unshown "
                            "root cause. In at most two sentences, state what happened and "
                            "one next debugging or fix action grounded in those facts."
                        ),
                    },
                    {"role": "user", "content": context},
                ],
            )
            explanation = completion.choices[0].message.content
            if explanation and explanation.strip():
                return explanation.strip()
            raise ValueError("Groq returned an empty explanation")
        except Exception:
            logger.exception(
                "Groq explanation failed for step %s; using rule-based fallback.",
                issue.step_id,
            )
            return self.fallback.explain(issue)


def create_explainer() -> Explainer:
    """Choose the configured provider, retaining a fully offline default."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.info(
            "TraceLens explainer mode: rule-based fallback (GROQ_API_KEY is not set)."
        )
        return RuleBasedExplainer()

    try:
        explainer = GroqExplainer(api_key)
    except ImportError:
        logger.warning(
            "TraceLens explainer mode: rule-based fallback (Groq SDK is unavailable)."
        )
        return RuleBasedExplainer()

    logger.info("TraceLens explainer mode: Groq (%s).", explainer.model)
    return explainer
