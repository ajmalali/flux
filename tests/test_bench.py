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

    def test_report_renders_delivery_next_to_efficiency(self):
        manifest, rows = self._rows()
        text = report.render_markdown(manifest, report.summarize(manifest, rows))
        self.assertIn("delivered", text)
        self.assertIn("Efficiency without delivery is not a win.", text)


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
