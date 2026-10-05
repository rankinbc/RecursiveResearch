import unittest

from helpers import WorkspaceCase
from rrlib import store


class SlugTests(unittest.TestCase):
    def test_slug_is_lowercase_and_hyphenated(self):
        self.assertEqual(store.slugify("The Magic of Scheherazade (NES)"), "the-magic-of-scheherazade-nes")

    def test_slug_with_no_usable_characters_is_an_error(self):
        with self.assertRaises(store.RRError):
            store.slugify("東方")

    def test_slug_is_capped_at_60_characters(self):
        self.assertLessEqual(len(store.slugify("word " * 40)), 60)

    def test_type_id_splits_pascal_case(self):
        self.assertEqual(store.type_id("CharacterClass"), "character_class")
        self.assertEqual(store.type_id("HTTP header"), "http_header")

    def test_is_under_matches_whole_path_segments_only(self):
        self.assertTrue(store.is_under("wire/framing", "wire"))
        self.assertTrue(store.is_under("wire", "wire"))
        self.assertFalse(store.is_under("wireless", "wire"))


class ScaffoldTests(WorkspaceCase):
    def test_scaffold_creates_layout_and_default_plan(self):
        for sub in ("knowledge/entities", "knowledge/tree", "sessions"):
            self.assertTrue((self.ws / sub).is_dir(), sub)
        plan = store.load_plan(self.ws)
        self.assertEqual(plan["subject"], "Test Subject")
        self.assertEqual(plan["slug"], "test-subject")
        self.assertEqual(plan["controls"]["depth_cap"], 4)
        self.assertEqual(plan["controls"]["max_agents_per_wave"], 4)
        self.assertEqual(plan["controls"]["close_thresholds"],
                         {"min_new_facts": 3, "max_duplicate_share": 0.6, "max_weak_share": 0.8})
        self.assertEqual(plan["approvals"], {"plan": False, "entity_types": False})
        self.assertEqual(set(plan["stages"].values()), {"pending"})

    def test_scaffold_refuses_to_overwrite_an_existing_workspace(self):
        with self.assertRaises(store.RRError):
            store.scaffold(self.root, "Test Subject")

    def test_scaffold_finishes_a_workspace_left_without_a_plan(self):
        (self.root / "half-made" / "knowledge").mkdir(parents=True)
        result = store.scaffold(self.root, "Half Made")
        self.assertEqual(result["slug"], "half-made")
        self.assertEqual(store.load_plan(self.root / "half-made")["subject"], "Half Made")

    def test_scaffold_accepts_an_explicit_slug_for_non_latin_subjects(self):
        result = store.scaffold(self.root, "東方", slug="touhou")
        self.assertEqual(result["slug"], "touhou")
        self.assertEqual(store.load_plan(self.root / "touhou")["subject"], "東方")

    def test_workspace_lookup_fails_clearly_when_missing(self):
        with self.assertRaisesRegex(store.RRError, "run scaffold first"):
            store.workspace(self.root, "nope")

    def test_list_workspaces(self):
        store.scaffold(self.root, "Another")
        self.assertEqual(store.list_workspaces(self.root), ["another", "test-subject"])
        self.assertEqual(store.list_workspaces(self.root / "missing"), [])


class JsonTests(WorkspaceCase):
    def test_read_json_accepts_a_byte_order_mark(self):
        path = self.ws / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}')
        self.assertEqual(store.read_json(path), {"a": 1})

    def test_read_json_reports_invalid_json_as_rrerror(self):
        path = self.write("bad.json", "{not json")
        with self.assertRaisesRegex(store.RRError, "not valid JSON"):
            store.read_json(path)

    def test_read_json_reports_a_missing_file_as_rrerror(self):
        with self.assertRaisesRegex(store.RRError, "missing file"):
            store.read_json(self.ws / "absent.json")

    def test_write_json_leaves_no_temporary_files(self):
        store.write_json(self.ws / "x.json", {"名前": "値"})
        self.assertEqual(store.read_json(self.ws / "x.json"), {"名前": "値"})
        self.assertEqual(list(self.ws.glob("*.tmp")), [])

    def test_a_hand_edited_plan_missing_sections_loads_with_defaults(self):
        plan = store.load_plan(self.ws)
        del plan["controls"]["close_thresholds"]
        del plan["controls"]["max_agents_per_wave"]
        del plan["branches"]
        plan["goal"] = "kept"
        store.save_plan(self.ws, plan)
        loaded = store.load_plan(self.ws)
        self.assertEqual(loaded["controls"]["max_agents_per_wave"], 4)
        self.assertEqual(loaded["controls"]["close_thresholds"]["min_new_facts"], 3)
        self.assertEqual(loaded["controls"]["depth_cap"], 4)
        self.assertEqual(loaded["branches"], {})
        self.assertEqual(loaded["goal"], "kept")

    def test_a_plan_that_is_not_an_object_is_an_rrerror(self):
        store.write_json(self.ws / "plan.json", ["oops"])
        with self.assertRaisesRegex(store.RRError, "must be a JSON object"):
            store.load_plan(self.ws)

    def test_set_stage_rejects_unknown_values(self):
        store.set_stage(self.ws, "survey", "done")
        self.assertEqual(store.load_plan(self.ws)["stages"]["survey"], "done")
        with self.assertRaises(store.RRError):
            store.set_stage(self.ws, "survey", "finished")
        with self.assertRaises(store.RRError):
            store.set_stage(self.ws, "nonsense", "done")


if __name__ == "__main__":
    unittest.main()
