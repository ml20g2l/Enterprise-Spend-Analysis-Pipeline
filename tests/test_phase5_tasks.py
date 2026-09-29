from pathlib import Path
import unittest

from src.orchestration.phase5_tasks import force_failure_target, required_project_files, safe_run_id


class Phase5TaskTests(unittest.TestCase):
    def tearDown(self):
        import os
        os.environ.pop("PHASE5_RUN_ID", None)
        os.environ.pop("PHASE5_FORCE_FAILURE", None)

    def test_run_id_is_safe_for_a_directory(self):
        import os
        os.environ["PHASE5_RUN_ID"] = "manual__2026-09-29T10:00:00+00:00"
        self.assertEqual(safe_run_id(), "manual__2026-09-29T10_00_00_00_00")

    def test_failure_target_rejects_shell_or_unknown_values(self):
        import os
        os.environ["PHASE5_FORCE_FAILURE"] = "reconciliation; echo unsafe"
        with self.assertRaises(RuntimeError):
            force_failure_target()

    def test_required_project_files_are_present(self):
        project_root = Path(__file__).resolve().parents[1]
        self.assertTrue(all(path.is_file() for path in required_project_files(project_root)))


if __name__ == "__main__":
    unittest.main()
