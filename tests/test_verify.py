import functools
import http.server
import threading
import unittest

from helpers import WorkspaceCase, proposal, raw_result
from rrlib import store, tasks, verify

PAGE = """<html><body><h1>Wire spec</h1>
<p>A frame MUST NOT exceed
   16384 bytes.</p>
<p>The server&rsquo;s reply is &ldquo;WELCOME&rdquo;.</p>
</body></html>"""


def finding(quote, **fields):
    base = {"claim": "a fact", "tier": "PRIMARY", "source": "the wire spec", "quote": quote}
    base.update(fields)
    return base


class VerifyTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.session = self.start_wave([proposal("p1")])
        self.page = self.write("local/spec.html", PAGE)
        self.calls = []
        real = verify.FETCH
        self.addCleanup(setattr, verify, "FETCH", real)

    def fake_fetch(self, pages):
        def fetch(url):
            self.calls.append(url)
            if url not in pages:
                raise OSError("certificate verify failed")
            return pages[url]
        verify.FETCH = fetch

    def run_verify(self, *findings):
        doc = raw_result("p1")
        doc["findings"] = list(findings)
        self.write(f"sessions/{self.session}/raw/p1.json", doc)
        summary = verify.verify_result(self.ws, self.session, "p1")
        return summary, store.read_json(self.ws / "sessions" / self.session / "raw" / "p1.json")["findings"]

    def test_a_quote_that_is_in_the_source_keeps_its_tier_and_is_marked_verified(self):
        summary, (f,) = self.run_verify(finding("A frame MUST NOT exceed 16384 bytes.", source_file=str(self.page)))
        self.assertEqual((summary["verified"], summary["downgraded"]), (1, 0))
        self.assertEqual((f["tier"], f["verified"]), ("PRIMARY", True))
        self.assertNotIn("downgraded_from", f)

    def test_a_quote_that_is_not_in_the_source_is_downgraded_with_the_reason(self):
        summary, (f,) = self.run_verify(finding("A frame MUST NOT exceed 1024 bytes.", source_file=str(self.page)))
        self.assertEqual((summary["verified"], summary["downgraded"]), (0, 1))
        self.assertEqual((f["tier"], f["downgraded_from"], f["verified"]), ("SECONDARY", "PRIMARY", False))
        self.assertIn("not found in the cited source", f["verify_note"])
        self.assertEqual(summary["notes"], [{"finding": 0, "note": f["verify_note"]}])

    def test_spacing_markup_entities_and_curly_quotes_do_not_defeat_a_real_quote(self):
        _, (a, b) = self.run_verify(
            finding("A frame  MUST NOT\nexceed 16384 bytes.", source_file=str(self.page)),
            finding("The server's reply is \"WELCOME\".", source_file=str(self.page)))
        self.assertEqual((a["tier"], b["tier"]), ("PRIMARY", "PRIMARY"))

    def test_a_short_fragment_is_not_enough_to_count_as_a_quote(self):
        _, (f,) = self.run_verify(finding("16384", source_file=str(self.page)))
        self.assertEqual(f["tier"], "SECONDARY")
        self.assertIn("too short", f["verify_note"])

    def test_a_source_that_cannot_be_fetched_by_the_script_is_downgraded(self):
        _, (a, b) = self.run_verify(finding("A frame MUST NOT exceed 16384 bytes."),
                                    finding("x" * 30, source="gemini://example.org/spec.gmi"))
        self.assertEqual((a["tier"], b["tier"]), ("SECONDARY", "SECONDARY"))
        self.assertIn("no source the script can open", a["verify_note"])

    def test_a_url_is_taken_from_source_url_or_from_the_source_text_and_fetched_once(self):
        self.fake_fetch({"https://example.org/spec": PAGE})
        summary, (a, b) = self.run_verify(
            finding("A frame MUST NOT exceed 16384 bytes.", source_url="https://example.org/spec"),
            finding("A frame MUST NOT exceed 16384 bytes.", source="Wire spec (https://example.org/spec), section 4"))
        self.assertEqual(summary["verified"], 2)
        self.assertEqual(self.calls, ["https://example.org/spec"])
        self.assertEqual(len(list((self.ws / "sessions" / self.session / "sources").glob("*.txt"))), 1)

    def test_a_fetch_failure_downgrades_and_says_why(self):
        self.fake_fetch({})
        _, (f,) = self.run_verify(finding("A frame MUST NOT exceed 16384 bytes.", source_url="https://down.example/spec"))
        self.assertEqual(f["tier"], "SECONDARY")
        self.assertIn("could not be fetched", f["verify_note"])
        self.assertIn("certificate verify failed", f["verify_note"])

    def test_other_tiers_are_left_exactly_as_they_were(self):
        before = {"claim": "c", "tier": "SECONDARY", "source": "a wiki", "quote": "anything"}
        summary, (f,) = self.run_verify(dict(before))
        self.assertEqual(f, before)
        self.assertEqual((summary["verified"], summary["downgraded"]), (0, 0))

    def test_verifying_twice_does_not_change_the_outcome(self):
        self.run_verify(finding("not in there at all, honestly", source_file=str(self.page)),
                        finding("A frame MUST NOT exceed 16384 bytes.", source_file=str(self.page)))
        summary = verify.verify_result(self.ws, self.session, "p1")
        findings = store.read_json(self.ws / "sessions" / self.session / "raw" / "p1.json")["findings"]
        self.assertEqual([f["tier"] for f in findings], ["SECONDARY", "PRIMARY"])
        self.assertEqual((summary["verified"], summary["downgraded"]), (1, 1))

    def test_a_real_http_fetch_works(self):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.ws / "local"))
        handler.log_message = lambda *args: None
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/spec.html"
        _, (f,) = self.run_verify(finding("A frame MUST NOT exceed 16384 bytes.", source_url=url))
        self.assertEqual((f["tier"], f["verified"]), ("PRIMARY", True))


class CompleteTaskVerifiesTests(WorkspaceCase):
    def test_completing_a_research_task_verifies_its_quotes_and_reports_the_counts(self):
        session = self.start_wave([proposal("p1")])
        page = self.write("local/spec.html", PAGE)
        doc = raw_result("p1", tiers=())
        doc["findings"] = [finding("A frame MUST NOT exceed 16384 bytes.", source_file=str(page)),
                           finding("A frame MUST NOT exceed 1024 bytes.", source_file=str(page))]
        self.write(f"sessions/{session}/raw/p1.json", doc)
        result = tasks.complete_task(self.ws, "p1", "done")
        self.assertEqual((result["quotes_verified"], result["quotes_downgraded"]), (1, 1))
        findings = store.read_json(self.ws / "sessions" / session / "raw" / "p1.json")["findings"]
        self.assertEqual([f["tier"] for f in findings], ["PRIMARY", "SECONDARY"])
        log = (self.ws / "sessions" / session / "activity.md").read_text(encoding="utf-8")
        self.assertIn("1 quote verified, 1 downgraded", log)


if __name__ == "__main__":
    unittest.main()
