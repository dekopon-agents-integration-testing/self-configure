import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os

os.environ.setdefault("GITHUB_RUN_ID", "local")
os.environ.setdefault("GITHUB_RUN_ATTEMPT", "1")
import run


class CommitVerification(unittest.TestCase):
    def check_history(self, files, count=1):
        def api(path):
            if "/compare/" in path:
                return {"commits": [{"sha": str(i)} for i in range(count)]}
            return {
                "files": [{"filename": f} for f in files],
                "parents": [{"sha": "seed"}],
            }

        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(run, "E", Path(d)),
            patch.object(run, "gh", api),
        ):
            return run.verify_commits("seed", "head")

    def test_single_agent_configuration_commit(self):
        self.check_history([run.PATH])

    def test_ci_change_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.check_history([run.PATH, ".github/workflows/self-configure.yml"])

    def test_missing_commit_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.check_history([run.PATH], 0)

    def test_four_commits_are_rejected(self):
        with self.assertRaises(AssertionError):
            self.check_history([run.PATH], 4)


class Reconciliation(unittest.TestCase):
    def test_child_not_created_yet_keeps_waiting(self):
        with patch.object(run, "k", return_value="") as kubectl:
            self.assertFalse(run.synced("catalog", "expected"))
            self.assertIn("--ignore-not-found", kubectl.call_args.args)

    def test_synced_wrong_revision_cannot_pass(self):
        with patch.object(run, "k", return_value='{"status":{"sync":{"status":"Synced","revision":"other"}}}'):
            self.assertFalse(run.synced("catalog", "expected"))

    def test_exact_synced_revision_passes(self):
        with patch.object(run, "k", return_value='{"status":{"sync":{"status":"Synced","revision":"expected"}}}'):
            self.assertTrue(run.synced("catalog", "expected"))


if __name__ == "__main__":
    unittest.main()
