import unittest

from helpers import WorkspaceCase
from rrlib import guard, store, tasks


class GuardTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]
        self.write("knowledge/spec.md", "original\n")

    def test_writing_only_to_raw_is_clean(self):
        self.assertEqual(guard.snapshot(self.ws), {"session": self.session, "files": 1})
        self.write(f"sessions/{self.session}/raw/s01.md", "section\n")
        self.assertEqual(guard.check_snapshot(self.ws),
                         {"session": self.session, "clean": True, "violations": []})

    def test_added_modified_and_removed_knowledge_files_are_violations(self):
        self.write("knowledge/tree/README.md", "tree\n")
        guard.snapshot(self.ws)
        self.write("knowledge/spec.md", "rewritten by a researcher\n")
        self.write("knowledge/tree/sneaky.md", "new\n")
        (self.ws / "knowledge/tree/README.md").unlink()
        result = guard.check_snapshot(self.ws)
        self.assertFalse(result["clean"])
        self.assertEqual(result["violations"], [
            {"file": "knowledge/spec.md", "change": "modified"},
            {"file": "knowledge/tree/README.md", "change": "removed"},
            {"file": "knowledge/tree/sneaky.md", "change": "added"},
        ])

    def test_checking_without_a_snapshot_is_an_error(self):
        with self.assertRaisesRegex(store.RRError, "missing file"):
            guard.check_snapshot(self.ws)


if __name__ == "__main__":
    unittest.main()
