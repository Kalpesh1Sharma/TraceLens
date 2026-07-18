"""Startup seeding checks for an empty TraceLens database."""

import os
import unittest
from unittest.mock import patch

import main
from storage import TraceStorage


class DemoSeedingTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_seeds_an_empty_database_only_once(self) -> None:
        original_storage = main.storage
        test_storage = TraceStorage("sqlite://")
        main.storage = test_storage
        try:
            with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
                async with main.lifespan(main.app):
                    self.assertFalse(test_storage.is_empty())
                    self.assertEqual(len(test_storage.get_run_events("demo-retry-loop")), 6)
                    self.assertEqual(len(test_storage.get_run_events("demo-tool-error")), 4)
                    self.assertEqual(len(test_storage.get_run_events("demo-mixed-failures")), 5)

                event_count_after_first_start = sum(
                    len(test_storage.get_run_events(run_id))
                    for run_id in (
                        "demo-retry-loop",
                        "demo-tool-error",
                        "demo-mixed-failures",
                    )
                )
                async with main.lifespan(main.app):
                    event_count_after_second_start = sum(
                        len(test_storage.get_run_events(run_id))
                        for run_id in (
                            "demo-retry-loop",
                            "demo-tool-error",
                            "demo-mixed-failures",
                        )
                    )
        finally:
            main.storage = original_storage

        self.assertEqual(event_count_after_first_start, 15)
        self.assertEqual(event_count_after_second_start, event_count_after_first_start)
