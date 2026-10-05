import copy
import unittest

from helpers import PLAN_FIELDS, SCHEMA, WorkspaceCase, proposal, raw_result
from rrlib import provenance, store, validate


def errors(issues):
    return [i["message"] for i in issues if i["level"] == "error"]


class ProvenanceTests(unittest.TestCase):
    def test_scan_counts_tier_tags_including_unknown_with_a_range(self):
        scan = provenance.scan_markdown("HP is 4 [PRIMARY]. Speed [UNKNOWN: est 3-5]. Also [PRIMARY].")
        self.assertEqual(scan["counts"]["PRIMARY"], 2)
        self.assertEqual(scan["counts"]["UNKNOWN"], 1)

    def test_scan_reports_legacy_tags_and_ignores_links_and_checkboxes(self):
        scan = provenance.scan_markdown("- [ ] todo\n- [x] done\nSee [API](http://x). Old [ROM_VERIFIED].")
        self.assertEqual(scan["unknown_tags"], ["ROM_VERIFIED"])
        self.assertEqual(sum(scan["counts"].values()), 0)

    def test_stronger_follows_the_fixed_precedence(self):
        self.assertEqual(provenance.stronger("SECONDARY", "PRIMARY"), "PRIMARY")
        self.assertEqual(provenance.stronger("EXPERT", "INFERRED"), "EXPERT")
        self.assertEqual(provenance.stronger("UNKNOWN", "OBSERVED"), "OBSERVED")


class PlanTests(WorkspaceCase):
    def plan(self, **overrides):
        plan = store.load_plan(self.ws)
        plan.update(copy.deepcopy(PLAN_FIELDS))
        plan.update(overrides)
        return plan

    def test_a_complete_plan_has_no_issues(self):
        self.assertEqual(validate.validate_plan(self.plan()), [])

    def test_a_fresh_scaffold_is_not_a_valid_plan(self):
        self.assertTrue(validate.has_errors(validate.validate_plan(store.load_plan(self.ws))))

    def test_plan_needs_a_goal_tasks_entity_types_and_a_mapped_source(self):
        issues = validate.validate_plan(self.plan(
            goal=" ", survey_tasks=[], entity_types=[],
            provenance_mapping={"PRIMARY": [], "EXPERT": [], "SECONDARY": []}))
        self.assertEqual({i["where"] for i in issues},
                         {"goal", "survey_tasks", "entity_types", "provenance_mapping"})

    def test_plan_rejects_sources_mapped_to_a_tier_that_takes_none(self):
        issues = validate.validate_plan(self.plan(provenance_mapping={"PRIMARY": ["x"], "INFERRED": ["y"]}))
        self.assertEqual([i["where"] for i in issues], ["provenance_mapping.INFERRED"])

    def test_plan_rejects_bad_controls(self):
        plan = self.plan()
        plan["controls"] = {"depth_cap": 0, "max_agents_per_wave": "4",
                            "close_thresholds": {"min_new_facts": -1, "max_duplicate_share": 1.5,
                                                 "max_weak_share": True}}
        self.assertEqual(len(errors(validate.validate_plan(plan))), 5)


class EntityTests(unittest.TestCase):
    def roster(self, **entity):
        base = {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY"}
        base.update(entity)
        return {"entity_type": "MessageType", "count": 1, "entities": [base]}

    def test_schema_is_valid(self):
        self.assertEqual(validate.validate_entity_schema(SCHEMA), [])

    def test_schema_rejects_types_that_would_share_a_file_name(self):
        doc = {"entity_types": [dict(SCHEMA["entity_types"][0]),
                                dict(SCHEMA["entity_types"][0], name="message_type")]}
        self.assertIn("message_type.json", errors(validate.validate_entity_schema(doc))[0])

    def test_schema_rejects_an_empty_list_and_types_without_properties(self):
        self.assertTrue(errors(validate.validate_entity_schema({"entity_types": []})))
        doc = {"entity_types": [{"name": "Thing", "description": "x", "properties": []}]}
        self.assertTrue(errors(validate.validate_entity_schema(doc)))

    def test_roster_with_one_tier_for_the_whole_entity_is_valid(self):
        self.assertEqual(validate.validate_entity_file(self.roster(), SCHEMA["entity_types"][0]), [])

    def test_roster_flags_values_without_a_tier(self):
        issues = validate.validate_entity_file(self.roster(provenance={"code": "PRIMARY"}),
                                               SCHEMA["entity_types"][0])
        self.assertEqual(errors(issues), ["property reply has no provenance tier"])

    def test_roster_requires_unknown_for_null_values(self):
        doc = self.roster(properties={"code": 1, "reply": None})
        self.assertIn("must be UNKNOWN", errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]))[0])
        doc = self.roster(properties={"code": 1, "reply": None},
                          provenance={"code": "PRIMARY", "reply": "UNKNOWN"})
        self.assertEqual(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]), [])

    def test_roster_flags_missing_extra_and_duplicate(self):
        doc = self.roster(properties={"code": 1, "colour": "red"})
        doc["entities"].append(copy.deepcopy(doc["entities"][0]))
        messages = errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]))
        self.assertIn("says 1 but there are 2 entities", messages[0])
        self.assertIn("missing property reply (use null if unknown)", messages)
        self.assertIn("property colour is not in the schema", messages)
        self.assertIn("appears more than once", messages)

    def test_an_empty_roster_is_an_error(self):
        doc = {"entity_type": "MessageType", "count": 0, "entities": []}
        self.assertTrue(errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0])))

    def test_find_type_by_id(self):
        self.assertEqual(validate.find_type(SCHEMA, "message_type")["name"], "MessageType")
        with self.assertRaises(store.RRError):
            validate.find_type(SCHEMA, "ship")


class RawTests(unittest.TestCase):
    def test_a_continue_result_is_valid(self):
        self.assertEqual(validate.validate_raw(raw_result("p1"), "p1"), [])

    def test_result_must_belong_to_the_task(self):
        self.assertTrue(errors(validate.validate_raw(raw_result("p1"), "p2")))

    def test_each_verdict_needs_its_evidence(self):
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "exhausted", unknowns_remaining=["x"]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "irreducible", sources_searched=[]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "sufficient", verdict_reason=""))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "continue", proposals=[]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "done"))))
        for verdict in ("exhausted", "irreducible", "sufficient"):
            self.assertEqual(validate.validate_raw(raw_result("p1", verdict)), [], verdict)

    def test_findings_need_a_claim_a_real_tier_and_a_source(self):
        doc = raw_result("p1")
        doc["findings"] = [{"claim": "", "tier": "PRIMARY", "source": "x"},
                           {"claim": "a", "tier": "UNKNOWN", "source": "x"},
                           {"claim": "b", "tier": "PRIMARY", "source": " ", "quote": "q"}]
        self.assertEqual(len(errors(validate.validate_raw(doc))), 3)

    def test_a_primary_finding_needs_the_exact_quote_but_other_tiers_do_not(self):
        doc = raw_result("p1")
        doc["findings"][0]["quote"] = "  "
        self.assertEqual(len(errors(validate.validate_raw(doc))), 1)
        self.assertIn("quote", errors(validate.validate_raw(doc))[0])
        doc["findings"][0]["tier"] = "SECONDARY"
        del doc["findings"][0]["quote"]
        self.assertEqual(validate.validate_raw(doc), [])

    def test_a_result_that_is_not_an_object_is_an_error(self):
        self.assertTrue(errors(validate.validate_raw(["nope"])))


class ProposalTests(WorkspaceCase):
    def check(self, *proposals, **branches):
        plan = store.load_plan(self.ws)
        plan["branches"] = branches
        return errors(validate.validate_proposals({"proposals": list(proposals)}, plan))

    def test_a_concrete_proposal_is_valid(self):
        self.assertEqual(self.check(proposal("p1")), [])

    def test_vague_unknowns_are_rejected(self):
        for text in ("Research this topic further", "More detail about framing", "tbd"):
            self.assertTrue(self.check(proposal("p1", unknown_being_resolved=text)), text)

    def test_concrete_unknowns_that_happen_to_say_further_or_deeper_are_accepted(self):
        for text in ("Whether further retries occur after a timeout",
                     "How much deeper the nesting limit is in version 2"):
            self.assertEqual(self.check(proposal("p1", unknown_being_resolved=text)), [], text)

    def test_proposal_needs_sources_and_a_target_inside_its_branch(self):
        self.assertTrue(self.check(proposal("p1", expected_sources=[])))
        self.assertTrue(self.check(proposal("p1", target_file="knowledge/tree/other/p1.md")))
        self.assertTrue(self.check(proposal("p1", target_file="knowledge/spec.md")))
        self.assertTrue(self.check(proposal("p1", branch="../escape")))

    def test_level_past_the_depth_cap_is_rejected(self):
        self.assertEqual(self.check(proposal("p1", level=4)), [])
        self.assertIn("past the depth cap of 4", self.check(proposal("p1", level=5))[0])

    def test_proposals_on_a_closed_branch_are_rejected_but_its_sub_branches_stay_open(self):
        closed = {"wire/framing": {"status": "closed", "reason": "exhausted"}}
        self.assertIn("is closed", self.check(proposal("p1"), **closed)[0])
        self.assertEqual(self.check(proposal("p1", branch="wire/framing/sub"), **closed), [])
        self.assertEqual(self.check(proposal("p1", branch="wire"), **closed), [])
        self.assertEqual(self.check(proposal("p1", branch="wire/framing2"), **closed), [])

    def test_duplicate_ids_and_bad_status_are_rejected(self):
        self.assertIn("duplicate id", self.check(proposal("p1"), proposal("p1")))
        self.assertTrue(self.check(proposal("p1", status="maybe")))

    def test_skipped_proposals_are_not_checked_further(self):
        self.assertEqual(self.check(proposal("p1", status="skipped", unknown_being_resolved="")), [])


class TreeTests(WorkspaceCase):
    def test_missing_tree_is_an_error(self):
        self.assertTrue(errors(validate.validate_tree(self.ws / "knowledge" / "absent")))

    def test_every_folder_needs_a_readme_with_known_unknowns(self):
        self.write("knowledge/tree/README.md", "# Tree [PRIMARY]\n\n## Known Unknowns\n")
        self.write("knowledge/tree/wire/README.md", "# Wire [PRIMARY]\n")
        (self.ws / "knowledge/tree/empty").mkdir()
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual(sorted(i["where"] for i in issues), ["empty", "wire/README.md"])

    def test_leaves_need_provenance(self):
        self.write("knowledge/tree/README.md", "# Tree\n\n## Known Unknowns\n")
        self.write("knowledge/tree/frame_sizes.json", {"_meta": {"provenance": "PRIMARY"}, "max": 9})
        self.write("knowledge/tree/handshake.md", "The client speaks first.\n")
        self.write("knowledge/tree/timeouts.json", {"_meta": {"provenance": "PRIMARY", "source": "RFC"}})
        self.write("knowledge/tree/retry.md", "Three retries [SECONDARY]. Legacy [GUIDE_SOURCED].\n")
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual({(i["level"], i["where"]) for i in issues}, {
            ("warning", "README.md"),
            ("error", "frame_sizes.json"),
            ("error", "handshake.md"),
            ("warning", "retry.md"),
        })

    def test_a_utf16_readme_in_the_tree_is_read_not_crashed_on(self):
        path = self.ws / "knowledge" / "tree" / "README.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("# Tree [PRIMARY]\n\n## Known Unknowns\n".encode("utf-16"))
        self.assertEqual(validate.validate_tree(self.ws / "knowledge" / "tree"), [])

    def test_generic_file_names_get_a_warning(self):
        self.write("knowledge/tree/README.md", "# Tree [PRIMARY]\n\n## Known Unknowns\n")
        self.write("knowledge/tree/data.json", {"_meta": {"provenance": "UNKNOWN"}})
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual([(i["level"], i["where"]) for i in issues], [("warning", "data.json")])


if __name__ == "__main__":
    unittest.main()
