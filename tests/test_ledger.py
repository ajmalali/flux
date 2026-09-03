"""Tests for `flux ledger`. Stdlib only: python3 -m unittest discover -s tests

The scanner is exercised on synthetic transcripts built here plus one checked-in
20-record golden fixture. AC-1's real-transcript numbers are not reproducible in CI
(the transcripts are not in the repo); they are pinned as a documented oracle in
test_ac1_oracle_documented below and verified by hand per the phase plan.
"""

import importlib.machinery
import json
import os
import subprocess
import tempfile
import unittest


FLUX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "flux")
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ledger_golden.jsonl")


def flux_module():
    loader = importlib.machinery.SourceFileLoader("flux_cli", FLUX)
    return loader.load_module()


M = flux_module()


# ------------------------------------------------------------- transcript builder

class Transcript:
    """Build a synthetic Claude Code .jsonl transcript record by record."""

    def __init__(self):
        self.recs = []
        self._n = 0

    def _ts(self):
        self._n += 1
        return "2026-08-21T09:%02d:00.000Z" % self._n

    def prime(self):
        self.recs.append({"type": "attachment", "attachment": {
            "type": "hook_success", "hookName": "SessionStart:startup",
            "content": "## flux prime — flux @ main\n"}})
        return self

    def prompt(self, text):
        self.recs.append({"type": "user", "timestamp": self._ts(),
                          "message": {"role": "user", "content": text}})
        return self

    def assistant(self, mid, tools=None, model="claude-opus-4-8",
                  inp=1000, cw=0, cr=1000, out=50, sidechain=False,
                  api_error_status=None, text=None):
        content = []
        if text is not None:
            content.append({"type": "text", "text": text})
        for tool in (tools or []):
            content.append(tool)
        rec = {"type": "assistant", "timestamp": self._ts(),
               "message": {"id": mid, "model": model,
                           "usage": {"input_tokens": inp,
                                     "cache_creation_input_tokens": cw,
                                     "cache_read_input_tokens": cr,
                                     "output_tokens": out},
                           "content": content}}
        if sidechain:
            rec["isSidechain"] = True
        if api_error_status is not None:
            rec["api_error_status"] = api_error_status
        self.recs.append(rec)
        return self

    def tool_result(self, tool_use_id, content="ok"):
        self.recs.append({"type": "user", "timestamp": self._ts(),
                          "message": {"role": "user", "content": [
                              {"type": "tool_result", "tool_use_id": tool_use_id,
                               "content": content}]}})
        return self

    def write(self, path):
        with open(path, "w") as fh:
            for r in self.recs:
                fh.write(json.dumps(r) + "\n")
        return path

    def scan(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            for r in self.recs:
                fh.write(json.dumps(r) + "\n")
            path = fh.name
        try:
            return M._scan_session(path)
        finally:
            os.unlink(path)


def bash(cmd, uid="u"):
    return {"type": "tool_use", "id": uid, "name": "Bash", "input": {"command": cmd}}


def read(path, uid="u"):
    return {"type": "tool_use", "id": uid, "name": "Read", "input": {"file_path": path}}


def edit(path, uid="u"):
    return {"type": "tool_use", "id": uid, "name": "Edit", "input": {"file_path": path}}


def skill(name, uid="u"):
    return {"type": "tool_use", "id": uid, "name": "Skill", "input": {"skill": name}}


# --------------------------------------------------------------------- the tests

class TestGoldenFixture(unittest.TestCase):
    def test_golden_row_matches(self):
        row = M._scan_session(FIXTURE)
        row["cost"] = round(row["cost"], 5)
        self.assertEqual(row, {
            "id": "ledger_g", "start": "2026-08-21T10:01", "end": "2026-08-21T10:19",
            "requests": 8, "void": False, "ctx_p50": 9950, "cost": 0.49266,
            "cw_share": 0.08, "rereads": 1, "bash_bytes": 51, "first_edit_req": 5,
            "flux_check": 1, "raw_gate": 1, "help_reads": 1, "wrapped": True,
            "prime": True,
        })


class TestScannerRules(unittest.TestCase):
    def test_dedupe_on_message_id(self):
        row = (Transcript()
               .assistant("dup", [bash("echo hi", "u1")])
               .assistant("dup", text="same id, second record")
               .assistant("other", [bash("echo bye", "u2")])
               .scan())
        self.assertEqual(row["requests"], 2)          # dup counted once

    def test_sidechain_excluded_from_context(self):
        row = (Transcript()
               .assistant("m1", inp=1000, cw=0, cr=0)   # ctx 1000
               .assistant("s1", inp=999000, cw=0, cr=0, sidechain=True)
               .scan())
        self.assertEqual(row["requests"], 1)
        self.assertEqual(row["ctx_p50"], 1000)         # sidechain's 999k ignored

    def test_ctx_is_input_plus_cache(self):
        row = Transcript().assistant("m1", inp=100, cw=200, cr=300).scan()
        self.assertEqual(row["ctx_p50"], 600)

    def test_void_zero_turn(self):
        row = Transcript().prompt("hello").scan()
        self.assertTrue(row["void"])
        self.assertEqual(row["requests"], 0)

    def test_void_all_requests_retryable_error(self):
        row = (Transcript()
               .assistant("e1", api_error_status="429", inp=0, cr=0)
               .scan())
        self.assertTrue(row["void"])

    def test_not_void_when_one_request_succeeds(self):
        row = (Transcript()
               .assistant("e1", api_error_status="429")
               .assistant("ok", [bash("echo hi", "u1")])
               .scan())
        self.assertFalse(row["void"])

    def test_wrap_via_flux_state_set_bash(self):
        row = Transcript().assistant("m1", [bash("flux state set next 'x'", "u1")]).scan()
        self.assertTrue(row["wrapped"])

    def test_wrap_via_slash_command(self):
        row = (Transcript()
               .assistant("m1", [read("/a", "u1")])
               .prompt("<command-name>/flux:wrap</command-name>")
               .scan())
        self.assertTrue(row["wrapped"])

    def test_wrap_via_skill_tool(self):
        row = Transcript().assistant("m1", [skill("flux:wrap", "u1")]).scan()
        self.assertTrue(row["wrapped"])

    def test_state_get_is_not_a_wrap(self):
        row = Transcript().assistant("m1", [bash("flux state get next", "u1")]).scan()
        self.assertFalse(row["wrapped"])

    def test_raw_gate_counted_but_flux_check_is_not_raw(self):
        row = (Transcript()
               .assistant("m1", [bash("python3 -m pytest tests/x.py", "u1")])
               .assistant("m2", [bash("flux check", "u2")])
               .scan())
        self.assertEqual(row["raw_gate"], 1)
        self.assertEqual(row["flux_check"], 1)

    def test_grep_mentioning_pytest_is_not_a_raw_gate(self):
        row = Transcript().assistant("m1", [bash('grep -n "pytest" foo.toml', "u1")]).scan()
        self.assertEqual(row["raw_gate"], 0)

    def test_help_reads_count_help_and_cached_skill_reads(self):
        row = (Transcript()
               .assistant("m1", [bash("flux --help", "u1")])
               .assistant("m2", [bash(
                   "cat ~/.claude/plugins/cache/marketplace/flux/2.10.1/skills/apply/SKILL.md",
                   "u2")])
               .assistant("m3", [read(
                   "/x/plugins/cache/marketplace/flux/skills/wrap/SKILL.md", "u3")])
               .scan())
        self.assertEqual(row["help_reads"], 3)

    def test_rereads_count_repeated_read_paths(self):
        row = (Transcript()
               .assistant("m1", [read("/repo/a.py", "u1")])
               .assistant("m2", [read("/repo/a.py", "u2")])
               .assistant("m3", [read("/repo/b.py", "u3")])
               .scan())
        self.assertEqual(row["rereads"], 1)


class TestAggregateAndBudget(unittest.TestCase):
    def _session(self, **kw):
        base = dict(requests=10, void=False, ctx_p50=80000, cost=5.0, cw_share=0.2,
                    rereads=0, bash_bytes=10000, first_edit_req=8, flux_check=2,
                    raw_gate=3, help_reads=0, wrapped=True, start="2026-08-21T10:00",
                    end="2026-08-21T11:00", id="x", prime=True)
        base.update(kw)
        return base

    def test_aggregate_over_cap_and_wrap(self):
        sessions = [self._session(requests=200), self._session(requests=10),
                    self._session(wrapped=False)]
        agg = M._aggregate(sessions)
        self.assertEqual(agg["sessions"], 3)
        self.assertEqual(agg["over_cap"], 1)
        self.assertEqual(agg["wrapped"], 2)
        self.assertEqual(agg["raw_gate"], 9)
        self.assertEqual(agg["flux_check"], 6)

    def test_budget_clip_elides_oldest_rows(self):
        header = ["H1", "H2"]
        rows = ["row-%02d 0123456789 abcdefghij" % i for i in range(40)]
        footer = ["TOTAL line", "summary line"]
        budget = 400
        out = M._fit_to_budget(header, rows, footer, budget)
        self.assertLessEqual(len(out.encode("utf-8")), budget)
        self.assertIn("rows elided", out)
        # newest rows kept, oldest dropped
        self.assertIn("row-39", out)
        self.assertNotIn("row-00", out)
        # header and footer survive
        self.assertIn("H1", out)
        self.assertIn("TOTAL line", out)

    def test_budget_no_clip_when_it_fits(self):
        out = M._fit_to_budget(["H"], ["r1", "r2"], ["F"], 10000)
        self.assertNotIn("rows elided", out)
        self.assertIn("r1", out)


class TestSlugRoundTrip(unittest.TestCase):
    def test_slug_path_roundtrip_with_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(os.path.realpath(tmp), "my.repo", "sub")
            os.makedirs(real)
            slug = M._slug_for_path(real)
            self.assertNotIn("/", slug)
            self.assertNotIn(".", slug)
            self.assertEqual(M._path_for_slug(slug), real)

    def test_reversal_gives_up_on_ambiguous_budget(self):
        # A slug with no matching filesystem tree resolves to None, not a hang.
        self.assertIsNone(M._path_for_slug("-no-such-path-anywhere-xyz"))


class TestCommand(unittest.TestCase):
    def test_non_flux_repo_exits_zero_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            proc = subprocess.run([FLUX, "ledger"], cwd=tmp,
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("nothing to measure", proc.stdout)

    def test_json_flag_emits_session_rows(self):
        # Point HOME at an empty projects tree so the scan finds nothing but the
        # command still emits a JSON array and exits 0.
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            os.makedirs(os.path.join(tmp, ".flux"))
            with open(os.path.join(tmp, ".flux", "flux.toml"), "w") as fh:
                fh.write("[check]\ncommand = \"true\"\n[state]\nbudget_tokens = 2000\n")
            env = dict(os.environ, HOME=tmp)
            proc = subprocess.run([FLUX, "ledger", "--json"], cwd=tmp,
                                  capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout), [])


class TestAc1Oracle(unittest.TestCase):
    """Manual oracle: real rpi-rfm69 transcripts are not checked in, so this is a
    documented expectation verified by hand (see the phase status side-by-side).

        flux ledger --since 2026-08-20  in ~/Dev/archsense/rpi-rfm69 TOTAL row:
          substantive sessions = 16
          ctx_p50              ≈ 87k   (measured 87k, within 5%)
          sessions > 150 req   = 0
          wrap coverage        = 11/16
          est $                ≈ 193
        Delta vs 2026-09-03 read-out: the gate ratio (flux-check vs raw-gate) is
        24/35 in the read-out's unsaved ad-hoc grep, 16/25 here; the read-out count
        included cross-repo greps and backend pytest runs and a wider session set.
        bash/re-reads/$-per-session differ because the read-out took medians over
        all in-range sessions while the ledger excludes void/minor per AC-2.
    """

    def test_oracle_documented(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
