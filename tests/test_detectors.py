"""Quick checks for the deliberately failing toy-agent traces."""

import unittest

from detectors import detect_issues
from toy_agent import build_demo_runs


class DetectorTests(unittest.TestCase):
    def test_toy_agent_failures_are_detected(self) -> None:
        demo_runs = build_demo_runs()
        retry_issues = detect_issues(demo_runs["demo-retry-loop"])
        error_issues = detect_issues(demo_runs["demo-tool-error"])

        retry_issue = next(
            issue for issue in retry_issues if issue.issue_type == "retry_loop"
        )
        self.assertEqual(retry_issue.step_id, "retry-search-3")
        self.assertEqual(len(retry_issue.events), 3)

        self.assertTrue(
            any(
                issue.issue_type == "tool_call_error" and issue.step_id == "error-parse"
                for issue in error_issues
            )
        )
        self.assertTrue(
            any(
                issue.issue_type == "silent_timeout" and issue.step_id == "error-respond"
                for issue in error_issues
            )
        )

    def test_mixed_support_run_detects_timeout_and_tool_error(self) -> None:
        mixed_issues = detect_issues(build_demo_runs()["demo-mixed-failures"])

        self.assertTrue(
            any(
                issue.issue_type == "silent_timeout"
                and issue.step_id == "support-draft-response"
                for issue in mixed_issues
            )
        )
        self.assertTrue(
            any(
                issue.issue_type == "tool_call_error"
                and issue.step_id == "support-send-response"
                for issue in mixed_issues
            )
        )


if __name__ == "__main__":
    unittest.main()
