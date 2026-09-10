"""Tests for the execution index (`flux task`). Stdlib only."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from test_flux_cli import FluxRepoCase, flux_module, run_flux


def iso_ago(seconds):
    t = time.time() - seconds
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"


class TaskCase(FluxRepoCase):
    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)

    def task(self, *args):
        return run_flux(["task"] + list(args), self.repo)

    def add(self, *args):
        out = self.task("add", *args)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def log_path(self):
        return os.path.join(self.repo, ".flux", "tasks.jsonl")

    def log_lines(self):
        with open(self.log_path()) as f:
            return [l for l in f.read().splitlines() if l.strip()]

    def append_raw(self, line):
        with open(self.log_path(), "a") as f:
            f.write(line + "\n")

    def budget(self, tokens):
        toml = os.path.join(self.repo, ".flux", "flux.toml")
        with open(toml) as f:
            body = f.read().replace("budget_tokens = 2000",
                                    "budget_tokens = %d" % tokens)
        with open(toml, "w") as f:
            f.write(body)


class TestTaskIds(TaskCase):
    def test_id_shape_and_determinism(self):
        mod = flux_module()
        first = mod.task_id("2026-09-10T09:14:03.221Z", "wire the reader")
        again = mod.task_id("2026-09-10T09:14:03.221Z", "wire the reader")
        self.assertEqual(first, again)
        self.assertRegex(first, r"^t-[a-z2-7]{4}$")
        self.assertNotEqual(first, mod.task_id("2026-09-10T09:14:03.222Z",
                                               "wire the reader"))

    def test_add_prints_the_id_alone(self):
        out = self.task("add", "wire the reader")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertRegex(out.stdout, r"^t-[a-z2-7]{4}\n$")


class TestTaskAddGuards(TaskCase):
    def test_title_is_required(self):
        self.assertEqual(self.task("add").returncode, 2)
        self.assertEqual(self.task("add", "   ").returncode, 2)
        self.assertEqual(self.task("add", "a", "b").returncode, 2)
        self.assertFalse(os.path.exists(self.log_path()))

    def test_title_over_120_characters_is_refused(self):
        out = self.task("add", "x" * 121)
        self.assertEqual(out.returncode, 2)
        self.assertIn("120", out.stderr)
        self.assertFalse(os.path.exists(self.log_path()))

    def test_record_cap_refuses_and_writes_nothing(self):
        """AC-5: an over-cap add leaves the log exactly as it was."""
        first = self.add("small one")
        before = self.log_lines()
        out = self.task("add", "big one", "--verify", "x" * 1100)
        self.assertEqual(out.returncode, 1)
        self.assertIn("TASK_RECORD_MAX_BYTES", out.stderr)
        self.assertEqual(self.log_lines(), before)
        self.assertIn(first, self.task("list").stdout)

    def test_dash_positional_is_refused(self):
        out = self.task("add", "--fils", "a.py")
        self.assertEqual(out.returncode, 2)
        self.assertIn("looks like a flag", out.stderr)
        self.assertFalse(os.path.exists(self.log_path()))

    def test_flag_without_a_value_is_a_usage_error(self):
        out = self.task("add", "title", "--verify")
        self.assertEqual(out.returncode, 2)
        self.assertIn("needs a value", out.stderr)

    def test_flag_values_are_verbatim(self):
        tid = self.add("title", "--verify", "-m pytest")
        self.assertIn("verify: -m pytest", self.task("next").stdout)
        self.assertTrue(tid)

    def test_no_config_is_exit_one(self):
        shutil.rmtree(os.path.join(self.repo, ".flux"))
        out = self.task("list")
        self.assertEqual(out.returncode, 1)
        self.assertIn("flux init", out.stderr)


class TestTaskLifecycle(TaskCase):
    def test_add_start_done_sequence(self):
        """AC-1, end to end."""
        a = self.add("A")
        b = self.add("B", "--blocked-by", a)
        rows = self.task("list").stdout
        self.assertIn("%s  open  A" % a, rows)
        self.assertIn("%s  open  B (blocked by %s)" % (b, a), rows)
        self.assertIn("2 open, 1 blocked, 0 done", rows)

        first = self.task("next").stdout
        self.assertEqual(first.split()[0], a)
        self.assertEqual(self.task("next").stdout, first)  # same input, same answer

        self.assertEqual(self.task("start", a).returncode, 0)
        rows = self.task("list").stdout
        self.assertIn("%s  active  A @" % a, rows)
        self.assertEqual(self.task("next").stdout.split()[0], a)

        self.assertEqual(self.task("done", a, "--by", "x").returncode, 0)
        rows = self.task("list", "--all").stdout
        self.assertIn("%s  done  A — by: x" % a, rows)
        self.assertIn("%s  open  B" % b, rows)
        self.assertNotIn("blocked by", rows)
        self.assertIn("1 open, 0 blocked, 1 done", rows)
        self.assertEqual(self.task("next").stdout.split()[0], b)

    def test_next_exits_one_when_nothing_is_runnable(self):
        a = self.add("A")
        self.task("done", a, "--by", "x")
        out = self.task("next")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no runnable task", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_next_all_lists_every_runnable_task_in_order(self):
        a = self.add("A", "--files", "a.py,b.py")
        b = self.add("B")
        c = self.add("C", "--blocked-by", b)
        out = self.task("next", "--all")
        self.assertEqual(out.returncode, 0)
        ids = [line.split()[0] for line in out.stdout.splitlines()]
        self.assertEqual(ids, [a, b])
        self.assertNotIn(c, out.stdout)
        self.assertIn("· files: a.py,b.py", out.stdout)

    def test_unknown_blocker_blocks_forever(self):
        a = self.add("A", "--blocked-by", "t-zzzz")
        self.assertIn("(blocked by ?t-zzzz)", self.task("list").stdout)
        self.assertEqual(self.task("next").returncode, 1)
        self.assertEqual(self.task("start", a).returncode, 1)

    def test_done_requires_by(self):
        a = self.add("A")
        out = self.task("done", a)
        self.assertEqual(out.returncode, 2)
        self.assertIn("--by", out.stderr)
        self.assertEqual(self.task("done", a, "--by", "  ").returncode, 2)

    def test_done_without_start_is_allowed_once(self):
        a = self.add("A")
        self.assertEqual(self.task("done", a, "--by", "read it").returncode, 0)
        out = self.task("done", a, "--by", "again")
        self.assertEqual(out.returncode, 1)
        self.assertIn("already done", out.stderr)

    def test_start_is_refused_on_blocked_done_and_unknown(self):
        a = self.add("A")
        b = self.add("B", "--blocked-by", a)
        out = self.task("start", b)
        self.assertEqual(out.returncode, 1)
        self.assertIn(a, out.stderr)
        self.task("done", a, "--by", "x")
        out = self.task("start", a)
        self.assertEqual(out.returncode, 1)
        self.assertIn("reopening is not a verb", out.stderr)
        self.assertEqual(self.task("start", "t-zzzz").returncode, 1)

    def test_garbage_lines_are_skipped(self):
        a = self.add("A")
        self.append_raw("not json at all")
        self.append_raw('{"ts": "x", "id": "t-oops"}')     # no op
        self.append_raw('{"ts": "x", "op": "done"}')       # no id
        self.append_raw('{"ts": "2026-01-01T00:00:00.000Z", "id": "t-ghos", '
                        '"op": "done", "by": "orphan"}')   # no add: an orphan
        rows = self.task("list", "--all").stdout
        self.assertIn(a, rows)
        self.assertNotIn("t-ghos", rows)
        self.assertIn("1 open, 0 blocked, 0 done", rows)

    def test_list_is_clipped_to_the_state_budget(self):
        for i in range(12):
            self.add("task number %d with a reasonably long title" % i)
        self.budget(20)  # 80 bytes
        out = self.task("list")
        self.assertEqual(out.returncode, 0)
        self.assertIn("[flux: truncated at budget]", out.stdout)

    def test_list_filters(self):
        a = self.add("A")
        b = self.add("B")
        self.task("start", b)
        c = self.add("C")
        self.task("done", c, "--by", "x")
        self.assertEqual(sorted(self.task("list", "--open").stdout.split("\n")[0:1]),
                         ["%s  open  A" % a])
        self.assertIn(b, self.task("list").stdout)
        self.assertNotIn(c, self.task("list").stdout)
        done = self.task("list", "--done").stdout
        self.assertIn("%s  done  C" % c, done)
        self.assertNotIn("  A", done)


class TestTaskCompaction(TaskCase):
    def test_compaction_folds_to_one_record_per_id(self):
        """AC-3: 9 records, 5 tasks."""
        done = [self.add("D%d" % i) for i in range(3)]
        for tid in done:
            self.task("done", tid, "--by", "v%s" % tid)
        active = self.add("Active")
        self.task("start", active)
        self.add("Open")
        self.assertEqual(len(self.log_lines()), 9)
        before = self.task("list", "--all").stdout

        out = self.task("compact")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("9 records -> 5", out.stdout)
        self.assertEqual(len(self.log_lines()), 5)
        self.assertEqual(self.task("list", "--all").stdout, before)

        with open(self.log_path()) as f:
            first = f.read()
        self.task("compact")
        with open(self.log_path()) as f:
            self.assertEqual(f.read(), first)  # byte-identical

    def test_compaction_of_an_absent_log_is_exit_one(self):
        out = self.task("compact")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no tasks.jsonl", out.stderr)

    def test_folded_records_replay_through_an_earlier_merged_start(self):
        """A clone that compacted after `done`, merged with a branch carrying an
        earlier `start`, must still replay to done."""
        a = self.add("A")
        self.task("done", a, "--by", "x")
        self.task("compact")
        self.append_raw(json.dumps({"ts": "2020-01-01T00:00:00.000Z", "id": a,
                                    "op": "start", "where": "other:w"}))
        rows = self.task("list", "--all").stdout
        self.assertIn("%s  done  A" % a, rows)

    def test_auto_compaction_past_eight_times_the_budget(self):
        self.budget(20)  # 80 bytes -> the log compacts past 640
        noise = []
        ids = []
        for i in range(4):
            out = self.task("add", "task %d with enough title to weigh something" % i)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertRegex(out.stdout, r"^t-[a-z2-7]{4}\n$")  # stdout is the id alone
            noise.append(out.stderr)
            ids.append(out.stdout.strip())
        for tid in ids:
            out = self.task("done", tid, "--by", "verified by the gate")
            self.assertEqual(out.returncode, 0, out.stderr)
            noise.append(out.stderr)
        self.assertTrue([n for n in noise if "compacted tasks.jsonl" in n],
                        "nothing reported an auto-compaction: %r" % noise)
        self.assertEqual(len(self.log_lines()), 4)  # one folded record per id


class TestTaskGitattributes(TaskCase):
    def path(self):
        return os.path.join(self.repo, ".flux", ".gitattributes")

    def test_init_writes_both_union_lines(self):
        with open(self.path()) as f:
            body = f.read()
        self.assertIn("state.jsonl merge=union", body)
        self.assertIn("tasks.jsonl merge=union", body)

    def test_missing_line_is_appended_to_an_existing_file(self):
        """AC-5, second half: a repo adopted before the index."""
        with open(self.path(), "w") as f:
            f.write("# hand written\nstate.jsonl merge=union")  # no trailing newline
        self.add("A")
        with open(self.path()) as f:
            body = f.read()
        self.assertIn("# hand written", body)
        self.assertEqual(body.count("state.jsonl merge=union"), 1)
        self.assertTrue(body.endswith("state.jsonl merge=union\ntasks.jsonl merge=union\n"))

    def test_append_is_idempotent(self):
        self.add("A")
        with open(self.path()) as f:
            body = f.read()
        self.add("B")
        with open(self.path()) as f:
            self.assertEqual(f.read(), body)


class TestTaskLeases(TaskCase):
    """Leases live under git's common dir, so every worktree of the repo sees them."""

    def setUp(self):
        super().setUp()
        self.lease_dir = os.path.join(self.repo, ".git", "flux", "leases")

    def lease_path(self, tid):
        return os.path.join(self.lease_dir, "%s.json" % tid)

    def seal(self, cwd=None):
        return run_flux(["seal"], cwd or self.repo,
                        stdin=json.dumps({"reason": "clear",
                                          "hook_event_name": "SessionEnd"}))

    def test_start_writes_a_lease_under_the_common_dir(self):
        a = self.add("A")
        self.task("start", a)
        self.assertTrue(os.path.isfile(self.lease_path(a)))
        with open(self.lease_path(a)) as f:
            lease = json.load(f)
        self.assertEqual(os.path.realpath(lease["worktree"]),
                         os.path.realpath(self.repo))
        self.assertIn(":", lease["where"])
        status = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("leases", status)

    def test_done_removes_the_lease(self):
        a = self.add("A")
        self.task("start", a)
        self.task("done", a, "--by", "x")
        self.assertFalse(os.path.exists(self.lease_path(a)))

    def test_seal_clears_this_worktrees_leases_and_unreadable_ones(self):
        a = self.add("A")
        self.task("start", a)
        os.makedirs(self.lease_dir, exist_ok=True)
        with open(self.lease_path("t-junk"), "w") as f:
            f.write("{not json")
        self.assertEqual(self.seal().returncode, 0)
        self.assertFalse(os.path.exists(self.lease_path(a)))
        self.assertFalse(os.path.exists(self.lease_path("t-junk")))

    def test_expired_lease_is_ignored(self):
        a = self.add("A")
        self.task("start", a)
        with open(self.lease_path(a), "w") as f:
            json.dump({"ts": iso_ago(13 * 3600), "where": "other:w",
                       "worktree": self.repo}, f)
        self.assertEqual(self.task("next").stdout.split()[0], a)
        self.assertEqual(self.task("start", a).returncode, 0)

    def test_lease_on_a_vanished_worktree_is_dead(self):
        a = self.add("A")
        with open(os.path.join(self.repo, ".flux", "tasks.jsonl"), "a") as f:
            f.write(json.dumps({"ts": "2026-09-10T00:00:00.000Z", "id": a,
                                "op": "start", "where": "other:gone"}) + "\n")
        os.makedirs(self.lease_dir, exist_ok=True)
        with open(self.lease_path(a), "w") as f:
            json.dump({"ts": iso_ago(60), "where": "other:gone",
                       "worktree": os.path.join(self.repo, "no-such-worktree")}, f)
        self.assertEqual(self.task("next").stdout.split()[0], a)

    def test_conflict_flag_after_two_starts_elsewhere(self):
        a = self.add("A")
        self.task("start", a)
        self.append_raw(json.dumps({"ts": "2026-09-11T00:00:00.000Z", "id": a,
                                    "op": "start", "where": "otherbox:clone"}))
        rows = self.task("list").stdout
        self.assertIn("[2 starts: ", rows)
        self.assertIn("otherbox:clone", rows)
        self.task("compact")
        self.assertIn("[2 starts: ", self.task("list").stdout)  # survives compaction


class TestTaskWorktrees(TaskCase):
    """AC-2. W2 lives outside self.repo — inside it, it would change the dirty count."""

    def setUp(self):
        super().setUp()
        self.a = self.add("A")
        subprocess.run(["git", "-C", self.repo, "add", "-f", ".flux"], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-q", "-m", "flux"], check=True)
        self._outer = tempfile.TemporaryDirectory()
        self.w2 = os.path.join(self._outer.name, "w2")
        subprocess.run(["git", "-C", self.repo, "worktree", "add", "-q",
                        self.w2, "-b", "w2"], check=True)

    def tearDown(self):
        subprocess.run(["git", "-C", self.repo, "worktree", "remove", "--force",
                        self.w2], capture_output=True)
        self._outer.cleanup()
        super().tearDown()

    def w2_task(self, *args):
        return run_flux(["task"] + list(args), self.w2)

    def test_lease_blocks_the_other_worktree_until_seal(self):
        self.assertEqual(self.w2_task("next").stdout.split()[0], self.a)

        self.assertEqual(self.task("start", self.a).returncode, 0)
        out = self.w2_task("next")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no runnable task", out.stderr)

        held = self.w2_task("start", self.a)
        self.assertEqual(held.returncode, 1)
        self.assertIn("held by", held.stderr)

        status = subprocess.run(["git", "-C", self.w2, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "")

        sealed = run_flux(["seal"], self.repo,
                          stdin=json.dumps({"reason": "clear",
                                            "hook_event_name": "SessionEnd"}))
        self.assertEqual(sealed.returncode, 0)
        out = self.w2_task("next")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.split()[0], self.a)


class TestTaskPrime(TaskCase):
    def prime(self):
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def commit(self, message):
        subprocess.run(["git", "-C", self.repo, "add", "-f", ".flux"], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@t", "-c",
                        "user.name=t", "commit", "-q", "-m", message], check=True)

    def test_open_task_replaces_the_phase_line(self):
        """AC-4a."""
        run_flux(["state", "set", "phase", "P1"], self.repo)
        a = self.add("wire the reader")
        pack = self.prime()
        self.assertIn("task: %s wire the reader · 1 open, 0 blocked, 0 done" % a, pack)
        self.assertNotIn("phase: P1", pack)
        self.assertIn("next: %s wire the reader  [from index — flux task next]" % a, pack)
        self.assertNotIn("(unset —", pack)

    def test_state_next_still_wins(self):
        run_flux(["state", "set", "next", "the stored one"], self.repo)
        self.add("the derived one")
        pack = self.prime()
        self.assertIn("next: the stored one", pack)
        self.assertNotIn("from index", pack)

    def test_all_done_index_is_byte_identical_to_no_index(self):
        """AC-4b. Both sides committed, so the header's dirty count matches."""
        run_flux(["state", "set", "phase", "P1", "position", "here"], self.repo)
        self.commit("state")
        baseline = self.prime()
        a = self.add("A")
        self.task("done", a, "--by", "x")
        self.commit("index")
        self.assertEqual(self.prime(), baseline)
        self.assertIn("phase: P1", baseline)

    def test_corrupt_index_leaves_the_pack_untouched(self):
        run_flux(["state", "set", "phase", "P1"], self.repo)
        self.commit("state")
        baseline = self.prime()
        with open(self.log_path(), "w") as f:
            f.write("this is not json\n")
        self.commit("garbage")
        self.assertEqual(self.prime(), baseline)

    def test_task_line_is_clipped_to_its_own_budget(self):
        self.append_raw(json.dumps({"ts": "2026-09-10T00:00:00.000Z", "id": "t-long",
                                    "op": "add", "title": "L" * 300}))
        line = [l for l in self.prime().splitlines() if l.startswith("task: ")][0]
        self.assertLessEqual(len(line.encode("utf-8")), 200)
        self.assertTrue(line.endswith("…"))

    def test_blocked_only_index_still_names_a_task_without_a_next(self):
        a = self.add("A", "--blocked-by", "t-zzzz")
        pack = self.prime()
        self.assertIn("task: %s A · 1 open, 1 blocked, 0 done" % a, pack)
        self.assertIn("(unset —", pack)  # nothing runnable: the stored hint stands


if __name__ == "__main__":
    unittest.main()
