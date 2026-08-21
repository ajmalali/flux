"""Tests for the benchmark harness in bench/.

These guard the properties that make a benchmark result mean anything. Two of
them are worth naming, because both have already been violated in practice:

* an arm that delivers nothing must never win a column (v1's ADR 0011);
* an acceptance suite must be red on the seed, or it measures nothing.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "bench"
sys.path.insert(0, str(BENCH))

from fluxbench import driver, metrics, report  # noqa: E402
from fluxbench.grade import ACCEPT_DIRNAME, grade  # noqa: E402
from fluxbench.spec import Arm, Project, available_arms, available_projects, render  # noqa: E402
from fluxbench.verify import verify_project  # noqa: E402


class PercentileTests(unittest.TestCase):
    def test_empty_sample_is_zero_not_an_error(self):
        self.assertEqual(metrics.percentile([], 50), 0)

    def test_nearest_rank(self):
        self.assertEqual(metrics.percentile([5], 50), 5)
        self.assertEqual(metrics.percentile([1, 2, 3, 4], 50), 2)
        self.assertEqual(metrics.percentile(list(range(1, 11)), 90), 9)


class ContextAccountingTests(unittest.TestCase):
    def test_context_counts_cache_reads(self):
        """A fully cached turn still had the whole context in front of it.
        Reading input_tokens alone would report ~2 tokens for a 30k context."""
        r = metrics.Request(input_tokens=2, cache_read_tokens=30000, cache_creation_tokens=0)
        self.assertEqual(r.context_tokens, 30002)

    def test_cache_write_share_is_of_weighted_spend(self):
        m = metrics.SessionMetrics(input_tokens=0, output_tokens=0,
                                   cache_creation_tokens=1000, cache_read_tokens=0)
        self.assertAlmostEqual(m.cache_write_share, 1.0)
        m2 = metrics.SessionMetrics(input_tokens=1250, output_tokens=0,
                                    cache_creation_tokens=1000, cache_read_tokens=0)
        self.assertAlmostEqual(m2.cache_write_share, 0.5)

    def test_envelope_prefers_model_usage_because_it_includes_subagents(self):
        payload = {
            "session_id": "abc", "duration_ms": 1000, "num_turns": 3,
            "total_cost_usd": 0.5, "subtype": "success", "is_error": False,
            "usage": {"input_tokens": 1, "output_tokens": 1,
                      "cache_read_input_tokens": 1, "cache_creation_input_tokens": 1},
            "modelUsage": {
                "claude-a": {"inputTokens": 10, "outputTokens": 20,
                             "cacheReadInputTokens": 30, "cacheCreationInputTokens": 40},
                "claude-b": {"inputTokens": 1, "outputTokens": 2,
                             "cacheReadInputTokens": 3, "cacheCreationInputTokens": 4},
            },
        }
        m = metrics.parse_result_envelope(payload, metrics.SessionMetrics())
        self.assertEqual((m.input_tokens, m.output_tokens), (11, 22))
        self.assertEqual((m.cache_read_tokens, m.cache_creation_tokens), (33, 44))
        self.assertTrue(m.ok)


class NoOpSessionTests(unittest.TestCase):
    """An unresolved slash command is the benchmark's most dangerous lie.

    Claude Code exits with is_error=false, subtype=success, zero turns and zero
    cost when a prompt resolves to nothing. Recorded naively, a misconfigured
    arm looks like a cheap, efficient one -- it scores well precisely because it
    did no work. This actually happened to the agentos arm."""

    @staticmethod
    def _envelope(**over):
        payload = {"session_id": "s", "subtype": "success", "is_error": False,
                   "num_turns": 0, "total_cost_usd": 0, "duration_ms": 0,
                   "modelUsage": {}}
        payload.update(over)
        return payload

    def test_zero_turn_zero_cost_session_is_not_ok(self):
        m = metrics.parse_result_envelope(self._envelope(), metrics.SessionMetrics())
        self.assertFalse(m.ok)
        self.assertIn("no turns", m.error)

    def test_a_real_session_is_still_ok(self):
        m = metrics.parse_result_envelope(
            self._envelope(num_turns=3, total_cost_usd=0.4), metrics.SessionMetrics())
        self.assertTrue(m.ok)

    def test_a_free_but_real_session_is_still_ok(self):
        """Zero cost alone is not proof of a no-op; zero turns with it is."""
        m = metrics.parse_result_envelope(
            self._envelope(num_turns=2, total_cost_usd=0), metrics.SessionMetrics())
        self.assertTrue(m.ok)


class TranscriptParsingTests(unittest.TestCase):
    def _write(self, entries):
        tmp = Path(tempfile.mkdtemp(prefix="fluxbench-t-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "t.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
        return path

    @staticmethod
    def _assistant(blocks, usage=None, sidechain=False):
        return {"type": "assistant", "isSidechain": sidechain,
                "message": {"model": "m", "content": blocks,
                            "usage": usage or {"input_tokens": 1, "output_tokens": 1,
                                               "cache_read_input_tokens": 0,
                                               "cache_creation_input_tokens": 0}}}

    @staticmethod
    def _result(tool_use_id, text, is_error=False):
        block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}
        if is_error:
            block["is_error"] = True
        return {"type": "user", "message": {"role": "user", "content": [block]}}

    def test_counts_tools_errors_bash_volume_and_repeat_reads(self):
        read = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/a.py"}}
        read_again = dict(read, id="t2")
        read_offset = {"type": "tool_use", "id": "t3", "name": "Read",
                       "input": {"file_path": "/a.py", "offset": 200}}
        bash = {"type": "tool_use", "id": "t4", "name": "Bash", "input": {"command": "ls"}}
        path = self._write([
            self._assistant([read]), self._result("t1", "x" * 10),
            self._assistant([read_again]), self._result("t2", "x" * 10),
            self._assistant([read_offset]), self._result("t3", "x" * 10),
            self._assistant([bash]), self._result("t4", "y" * 500, is_error=True),
        ])
        m = metrics.parse_transcript(path, metrics.SessionMetrics())
        self.assertEqual(m.tool_calls, {"Read": 3, "Bash": 1})
        self.assertEqual(m.tool_errors, 1)
        self.assertEqual(m.bash_output_chars, 500)
        self.assertEqual(m.tool_result_chars, 530)

    def test_paging_through_a_file_is_not_a_redundant_read(self):
        base = {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "/a.py"}}
        paged = {"type": "tool_use", "id": "b", "name": "Read",
                 "input": {"file_path": "/a.py", "offset": 2000}}
        m = metrics.parse_transcript(self._write([self._assistant([base]), self._assistant([paged])]),
                                     metrics.SessionMetrics())
        self.assertEqual(m.redundant_reads, 0)

    def test_identical_read_repeated_is_redundant(self):
        base = {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "/a.py"}}
        m = metrics.parse_transcript(
            self._write([self._assistant([base]), self._assistant([dict(base, id="b")]),
                         self._assistant([dict(base, id="c")])]),
            metrics.SessionMetrics())
        self.assertEqual(m.redundant_reads, 2)

    def test_subagent_requests_are_excluded_from_context_percentiles(self):
        big = {"input_tokens": 0, "output_tokens": 0,
               "cache_read_input_tokens": 500000, "cache_creation_input_tokens": 0}
        small = {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 0}
        m = metrics.parse_transcript(
            self._write([self._assistant([], small), self._assistant([], big, sidechain=True)]),
            metrics.SessionMetrics())
        self.assertEqual(m.subagent_requests, 1)
        self.assertEqual(m.context_percentile(50), 1000)


class FairnessTests(unittest.TestCase):
    """The driver, not the arm, owns everything that could hand someone an edge."""

    def test_every_session_gets_the_same_permissions_and_denials(self):
        argv = driver.build_argv("p", model="sonnet", effort=None, plugin_dirs=[],
                                 setting_sources="project", settings_file=None, max_usd=None)
        self.assertIn("bypassPermissions", argv)
        self.assertIn("AskUserQuestion", argv[argv.index("--disallowed-tools") + 1])
        self.assertIn("--setting-sources", argv)

    def test_arms_cannot_choose_their_own_model_or_effort(self):
        """Model and effort are run-level, not arm-level. If an arm spec could set
        them, a 'win' might only mean a bigger model."""
        forbidden = {"model", "effort", "permission_mode", "max_usd", "tools"}
        self.assertFalse(forbidden & set(Arm.__dataclass_fields__))

    def test_environment_is_scrubbed_of_the_parent_session(self):
        import os
        os.environ["CLAUDECODE"] = "1"
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        self.addCleanup(os.environ.pop, "CLAUDECODE", None)
        self.addCleanup(os.environ.pop, "CLAUDE_CODE_ENTRYPOINT", None)
        env = driver.child_env()
        self.assertNotIn("CLAUDECODE", env)
        self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", env)

    def test_all_shipped_arms_load_and_are_distinct(self):
        names = available_arms()
        self.assertTrue(names, "no arm specs shipped")
        arms = [Arm.load(n) for n in names]
        self.assertEqual(len({a.name for a in arms}), len(arms))
        for arm in arms:
            self.assertTrue(arm.steps, "%s has no steps" % arm.name)
            self.assertTrue(arm.notes.strip(), "%s must say what it is testing" % arm.name)

    def test_every_arm_is_told_the_same_thing_about_the_task(self):
        """Prompts may differ in procedure but must not differ in the task text.
        Substitution is shared, so a brief cannot be paraphrased for one arm."""
        project = Project.load("smoke")
        task = project.tasks[0]
        rendered = render("{task_id}|{brief_path}|{gate}", task, project, Path("/tmp/x"))
        self.assertEqual(rendered, "s1|TASK.md|%s" % project.gate)


class GradeTests(unittest.TestCase):
    def _seed(self):
        tmp = Path(tempfile.mkdtemp(prefix="fluxbench-g-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = tmp / "repo"
        shutil.copytree(BENCH / "projects" / "smoke" / "seed", repo)
        return repo

    def test_doing_nothing_scores_zero_not_full_marks(self):
        """The v1 failure mode: grading on the repo's own suite alone lets an arm
        that changed nothing score maximum quality at near-zero cost."""
        repo = self._seed()
        project = Project.load("smoke")
        task = project.tasks[0]
        result = grade(repo, task.accept_dir, project.accept_command, project.gate)
        self.assertTrue(result.gate_ran and result.gate_ok, "repo gate is green on an untouched tree")
        self.assertFalse(result.accept_ok)
        self.assertEqual(result.accept_passed, 0)
        self.assertFalse(result.delivered)

    def test_held_out_tests_never_stay_in_the_tree(self):
        repo = self._seed()
        project = Project.load("smoke")
        grade(repo, project.tasks[0].accept_dir, project.accept_command, "")
        self.assertFalse((repo / ACCEPT_DIRNAME).exists())

    def test_an_arm_planting_its_own_accept_dir_is_flagged(self):
        repo = self._seed()
        (repo / ACCEPT_DIRNAME).mkdir()
        (repo / ACCEPT_DIRNAME / "test_fake.py").write_text("", encoding="utf-8")
        project = Project.load("smoke")
        result = grade(repo, project.tasks[0].accept_dir, project.accept_command, "")
        self.assertTrue(result.contaminated)


class ReportTests(unittest.TestCase):
    @staticmethod
    def _rows():
        manifest = {"type": "manifest", "run_id": "t",
                    "config": {"model": "sonnet", "max_usd": 10},
                    "project": {"title": "p", "tasks": [{"id": "a"}]},
                    "arms": [{"name": "lazy"}, {"name": "worker"}]}
        rows = [
            {"type": "session", "arm": "lazy", "task": "a", "cost_usd": 0.01, "wall_ms": 1000,
             "input_tokens": 1, "output_tokens": 1, "cache_read_tokens": 1,
             "cache_creation_tokens": 1, "tool_calls": {}, "requests": [
                 {"input_tokens": 10, "cache_read_tokens": 0, "cache_creation_tokens": 0,
                  "sidechain": False}]},
            {"type": "task", "arm": "lazy", "task": "a", "delivered": False,
             "grade": {"accept_total": 5, "accept_passed": 0, "gate_ok": True}},
            {"type": "session", "arm": "worker", "task": "a", "cost_usd": 5.0, "wall_ms": 90000,
             "input_tokens": 100, "output_tokens": 100, "cache_read_tokens": 100,
             "cache_creation_tokens": 100, "tool_calls": {"Read": 4}, "tool_errors": 1,
             "requests": [{"input_tokens": 90000, "cache_read_tokens": 0,
                           "cache_creation_tokens": 0, "sidechain": False}]},
            {"type": "task", "arm": "worker", "task": "a", "delivered": True,
             "grade": {"accept_total": 5, "accept_passed": 5, "gate_ok": True}},
        ]
        return manifest, rows

    def test_an_arm_that_delivered_nothing_wins_no_column(self):
        manifest, rows = self._rows()
        summaries = report.summarize(manifest, rows)
        winners = report._winners(summaries)
        self.assertNotIn("lazy", set(winners.values()),
                         "the cheapest arm did nothing; it must not win a single metric")

    def test_bootstrap_cost_counts_but_does_not_pollute_context_stats(self):
        manifest, rows = self._rows()
        rows.append({"type": "session", "arm": "worker", "task": "bootstrap", "cost_usd": 1.0,
                     "wall_ms": 5000, "input_tokens": 999999, "requests": [
                         {"input_tokens": 999999, "cache_read_tokens": 0,
                          "cache_creation_tokens": 0, "sidechain": False}]})
        worker = [s for s in report.summarize(manifest, rows) if s.arm == "worker"][0]
        self.assertAlmostEqual(worker.cost_usd, 6.0)
        self.assertEqual(worker.median_context, 90000)

    def test_verdict_names_every_metric_the_focus_arm_loses(self):
        """The point of the exercise is that a bad answer triggers work, so the
        losses have to be spelled out rather than left to be read off a table."""
        manifest, rows = self._rows()
        manifest["arms"] = [{"name": "lazy"}, {"name": "worker"}]
        text = report.render_verdict(report.summarize(manifest, rows), focus="worker")
        self.assertIn("worker", text)
        self.assertIn("delivered", text)

    def test_verdict_says_so_when_the_focus_arm_delivered_nothing(self):
        manifest, rows = self._rows()
        text = report.render_verdict(report.summarize(manifest, rows), focus="lazy")
        self.assertIn("delivered nothing", text)
        self.assertIn("does not count" if "does not count" in text else "count", text)

    def test_verdict_declares_a_clean_sweep_when_there_is_one(self):
        manifest = {"run_id": "t", "config": {}, "project": {"tasks": []},
                    "arms": [{"name": "flux"}, {"name": "rival"}]}
        rows = [
            {"type": "session", "arm": "flux", "task": "a", "cost_usd": 1.0, "wall_ms": 10,
             "input_tokens": 1, "output_tokens": 1, "cache_read_tokens": 1,
             "cache_creation_tokens": 0, "tool_calls": {"Read": 10}, "tool_errors": 0,
             "requests": [{"input_tokens": 10, "cache_read_tokens": 0,
                           "cache_creation_tokens": 0, "sidechain": False}]},
            {"type": "task", "arm": "flux", "task": "a", "delivered": True,
             "grade": {"accept_total": 1, "accept_passed": 1, "gate_ok": True}},
            {"type": "session", "arm": "rival", "task": "a", "cost_usd": 9.0, "wall_ms": 900,
             "input_tokens": 100, "output_tokens": 100, "cache_read_tokens": 100,
             "cache_creation_tokens": 900, "tool_calls": {"Read": 10}, "tool_errors": 9,
             "redundant_reads": 8, "bash_output_chars": 90000,
             "requests": [{"input_tokens": 900, "cache_read_tokens": 0,
                           "cache_creation_tokens": 0, "sidechain": False}]},
            {"type": "task", "arm": "rival", "task": "a", "delivered": True,
             "grade": {"accept_total": 1, "accept_passed": 1, "gate_ok": True}},
        ]
        text = report.render_verdict(report.summarize(manifest, rows), focus="flux")
        self.assertIn("wins every measured column", text)

    def test_report_renders_delivery_next_to_efficiency(self):
        manifest, rows = self._rows()
        text = report.render_markdown(manifest, report.summarize(manifest, rows))
        self.assertIn("delivered", text)
        self.assertIn("Efficiency without delivery is not a win.", text)


class UnbriefedApiTests(unittest.TestCase):
    """A test may only hold an arm to API the brief names, or the seed already has."""

    def test_seed_scaffolding_is_allowed(self):
        from fluxbench.verify import seed_symbols, unbriefed_symbols

        project = Project.load("meridian")
        seed = seed_symbols(project)
        self.assertIn("BookingService", seed)
        self.assertIn("JsonStore", seed)
        for task in project.tasks:
            self.assertEqual(unbriefed_symbols(task, seed), [], task.id)

    def test_a_helper_nobody_asked_for_is_caught(self):
        from fluxbench.spec import Task
        from fluxbench.verify import unbriefed_symbols

        tmp = Path(tempfile.mkdtemp(prefix="fluxbench-u-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "test_x.py").write_text(
            "from meridian.domain.policy import invented_helper\n", encoding="utf-8")
        task = Task(id="x", title="x", brief="Add a policy module.", accept_dir=tmp)
        self.assertEqual(unbriefed_symbols(task, set()), ["invented_helper"])


class CorpusTests(unittest.TestCase):
    def test_every_shipped_project_is_fit_to_judge(self):
        """Red on the seed, green on the reference, gate intact -- for every task
        of every project in the corpus."""
        for name in available_projects():
            project = Project.load(name)
            with self.subTest(project=name):
                for verdict in verify_project(project):
                    self.assertTrue(
                        verdict.ok,
                        "%s/%s is not fit to judge an arm: %s"
                        % (name, verdict.task, verdict.detail or "missing acceptance or reference"))


if __name__ == "__main__":
    unittest.main()


class TransportFailureTests(unittest.TestCase):
    """A rate limit is not a result. This one cost a whole run to learn.

    In ``meridian-002`` the account hit its rate limit mid-run and 32 sessions
    came back in under a second with ``api_error_status: 429``. Every one was
    recorded as a session the arm had failed, and the report went on to state
    that ``paul`` and ``flux-lite`` delivered 0 of 4 -- a sentence about the API,
    printed as a sentence about the frameworks.
    """

    @staticmethod
    def _envelope(status="", cost=0.0, ok=False):
        return driver.SessionOutcome(
            ok=ok, payload={"total_cost_usd": cost}, stdout="", stderr="",
            wall_ms=1, argv=[], error=status, api_error_status=status)

    def test_rate_limit_on_a_free_attempt_is_retryable(self):
        self.assertTrue(driver.is_retryable(self._envelope("429")))

    def test_a_billed_attempt_is_never_retried(self):
        """It may already have written to the repo; a rerun would judge the arm
        against a tree its own abandoned attempt had moved."""
        self.assertFalse(driver.is_retryable(self._envelope("429", cost=0.52)))

    def test_a_successful_session_is_not_retried(self):
        self.assertFalse(driver.is_retryable(self._envelope(ok=True)))

    def test_a_refusal_or_model_error_is_a_result_not_a_transport_failure(self):
        self.assertFalse(driver.is_retryable(self._envelope("400")))

    def test_run_session_waits_out_a_rate_limit_and_returns_the_success(self):
        attempts = []
        slept = []
        envelopes = [
            driver.SessionOutcome(ok=False, payload={"total_cost_usd": 0}, stdout="",
                                  stderr="", wall_ms=1, argv=[], error="429",
                                  api_error_status="429"),
            driver.SessionOutcome(ok=True, payload={"total_cost_usd": 1.0}, stdout="",
                                  stderr="", wall_ms=1, argv=[], error=""),
        ]

        def fake_attempt(*a, **kw):
            attempts.append(1)
            return envelopes[len(attempts) - 1]

        original = driver._attempt
        driver._attempt = fake_attempt
        try:
            out = driver.run_session("p", Path("."), model="sonnet",
                                     backoff_s=[1, 2], sleep=slept.append)
        finally:
            driver._attempt = original
        self.assertTrue(out.ok)
        self.assertEqual(out.attempts, 2)
        self.assertEqual(slept, [1], "it must have waited before trying again")

    def test_run_session_gives_up_after_the_backoff_schedule(self):
        slept = []
        original = driver._attempt
        driver._attempt = lambda *a, **kw: driver.SessionOutcome(
            ok=False, payload={"total_cost_usd": 0}, stdout="", stderr="", wall_ms=1,
            argv=[], error="429", api_error_status="429")
        try:
            out = driver.run_session("p", Path("."), model="sonnet",
                                     backoff_s=[1, 2], sleep=slept.append)
        finally:
            driver._attempt = original
        self.assertFalse(out.ok)
        self.assertEqual(out.attempts, 3, "one attempt per wait, plus a final one")
        self.assertEqual(slept, [1, 2])
        self.assertEqual(out.api_error_status, "429")


class VoidTaskTests(unittest.TestCase):
    """A task nobody got to attempt must be excluded, never scored zero."""

    @staticmethod
    def _rows():
        manifest = {"type": "manifest", "run_id": "t",
                    "config": {"model": "sonnet", "max_usd": 10},
                    "project": {"title": "p", "tasks": [{"id": "a"}, {"id": "b"}]},
                    "arms": [{"name": "flux"}, {"name": "downed"}]}
        rows = [
            {"type": "session", "arm": "flux", "task": "a", "cost_usd": 2.0, "wall_ms": 60000,
             "input_tokens": 10, "output_tokens": 10, "cache_read_tokens": 10,
             "cache_creation_tokens": 10, "tool_calls": {"Read": 2},
             "requests": [{"input_tokens": 50000, "cache_read_tokens": 0,
                           "cache_creation_tokens": 0, "sidechain": False}]},
            {"type": "task", "arm": "flux", "task": "a", "delivered": True,
             "grade": {"accept_total": 5, "accept_passed": 5, "gate_ok": True}},
            # task b never ran: the session died on a 429 and the task is void
            {"type": "session", "arm": "flux", "task": "b", "cost_usd": 0.0, "wall_ms": 300,
             "ok": False, "api_error_status": "429", "tool_calls": {},
             "requests": []},
            {"type": "task", "arm": "flux", "task": "b", "delivered": False,
             "void": "429 -- the arm was not given the chance to try"},
            {"type": "task", "arm": "downed", "task": "a", "void": "429"},
            {"type": "task", "arm": "downed", "task": "b", "void": "arm abandoned after a"},
        ]
        return manifest, rows

    def _arm(self, name):
        manifest, rows = self._rows()
        return [s for s in report.summarize(manifest, rows) if s.arm == name][0]

    def test_a_void_task_is_not_a_failure_to_deliver(self):
        flux = self._arm("flux")
        self.assertEqual(flux.tasks, 1, "only the attempted task is scored")
        self.assertEqual(flux.void_tasks, 1)
        self.assertEqual(flux.delivered, "1/1 (+1 void)")

    def test_a_void_session_does_not_drag_down_the_metrics(self):
        """The 0.3s rate-limited session would otherwise halve $/task and
        pull the median context toward zero -- flattering the arm for a
        failure that was not its own."""
        flux = self._arm("flux")
        self.assertAlmostEqual(flux.cost_per_task, 2.0)
        self.assertEqual(flux.median_context, 50000)

    def test_an_arm_that_never_ran_is_void_not_zero(self):
        downed = self._arm("downed")
        self.assertFalse(downed.scored)
        self.assertEqual(downed.delivered, "void")

    def test_a_void_arm_is_not_ticked_against_every_target(self):
        manifest, rows = self._rows()
        text = report.render_markdown(manifest, report.summarize(manifest, rows))
        targets = text.split("## against plan.md targets")[1].split("##")[0]
        for line in targets.splitlines():
            if line.startswith("| $/task") or line.startswith("| ctx p50"):
                self.assertNotIn("$0.00 ✓", line)
                self.assertIn("—", line, "an arm that never ran hits no target")

    def test_the_report_says_the_run_is_incomplete(self):
        manifest, rows = self._rows()
        text = report.render_markdown(manifest, report.summarize(manifest, rows))
        self.assertIn("This run is incomplete", text)
        self.assertIn("| downed | 0 | 2 |", text)

    def test_the_verdict_compares_on_shared_tasks_not_unequal_totals(self):
        """`vanilla` scoring 4 tasks and `flux` 2 is not `flux` being
        out-delivered -- it is two different experiments. The tasks they both
        attempted are still a comparison, and the only one the run earned."""
        manifest = {"type": "manifest", "run_id": "t",
                    "config": {"model": "sonnet", "max_usd": 10},
                    "project": {"title": "p", "tasks": [{"id": "a"}, {"id": "b"}]},
                    "arms": [{"name": "flux"}, {"name": "vanilla"}]}
        rows = [
            {"type": "session", "arm": "flux", "task": "a", "cost_usd": 2.0,
             "tool_calls": {}, "requests": []},
            {"type": "task", "arm": "flux", "task": "a", "delivered": True,
             "grade": {"accept_total": 1, "accept_passed": 1, "gate_ok": True}},
            {"type": "task", "arm": "flux", "task": "b", "void": "429"},
            {"type": "session", "arm": "vanilla", "task": "a", "cost_usd": 1.0,
             "tool_calls": {}, "requests": []},
            {"type": "task", "arm": "vanilla", "task": "a", "delivered": True,
             "grade": {"accept_total": 1, "accept_passed": 1, "gate_ok": True}},
            {"type": "session", "arm": "vanilla", "task": "b", "cost_usd": 1.0,
             "tool_calls": {}, "requests": []},
            {"type": "task", "arm": "vanilla", "task": "b", "delivered": True,
             "grade": {"accept_total": 1, "accept_passed": 1, "gate_ok": True}},
        ]
        text = report.render_verdict(report.summarize(manifest, rows), focus="flux")
        self.assertIn("Read this run as incomplete", text)
        self.assertIn("scored different tasks", text)
        self.assertIn("| `vanilla` | a | 1/1 | 1/1 |", text,
                      "the shared task is the one honest comparison available")
        self.assertNotIn("Out-delivered", text)
