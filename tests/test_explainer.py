"""Tests for the offline explanation path."""

import os
import unittest
from unittest.mock import patch

from detectors import detect_issues
from explainer import RuleBasedExplainer, create_explainer
from toy_agent import build_demo_runs


class ExplainerTests(unittest.TestCase):
    def test_fallback_explains_toy_agent_failures_without_api_key(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertLogs("explainer", level="INFO") as logs:
                explainer = create_explainer()

        self.assertIsInstance(explainer, RuleBasedExplainer)
        self.assertIn("rule-based fallback", "\n".join(logs.output))

        demo_runs = build_demo_runs()
        retry_issue = next(
            issue
            for issue in detect_issues(demo_runs["demo-retry-loop"])
            if issue.issue_type == "retry_loop"
        )
        tool_error_issue = next(
            issue
            for issue in detect_issues(demo_runs["demo-tool-error"])
            if issue.issue_type == "tool_call_error"
        )

        self.assertTrue(explainer.explain(retry_issue).strip())
        self.assertTrue(explainer.explain(tool_error_issue).strip())
