"""Tests for bin/flux. Stdlib only: python3 -m unittest discover -s tests"""

import importlib.machinery
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

def flux_module():
    """Import bin/flux (extensionless) so tests can sweep its rule table."""
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "flux_cli", importlib.machinery.SourceFileLoader("flux_cli", FLUX))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FLUX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "flux")


def run_flux(args, cwd, env_extra=None, stdin=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [FLUX] + args, cwd=cwd, capture_output=True, text=True, env=env, timeout=60,
        input=stdin,
    )


class FluxRepoCase(unittest.TestCase):
    """A temp git repo per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        subprocess.run(
            ["git", "-C", self.repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "root"], check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def candidate(self):
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            return f.read()

    def write(self, rel, content):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path


class TestInit(FluxRepoCase):
    def test_detects_uv_python(self):
        self.write("uv.lock", "")
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("uv.lock", out.stdout)
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            self.assertIn("uv run ruff check", f.read())
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".flux", "state.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".flux", ".gitignore")))

    def test_init_writes_the_union_merge_attribute(self):
        """Without it the log conflicts exactly like the file it replaced."""
        run_flux(["init"], self.repo)
        with open(os.path.join(self.repo, ".flux", ".gitattributes")) as f:
            self.assertIn("state.jsonl merge=union", f.read())

    def test_detected_command_is_a_candidate(self):
        self.write("uv.lock", "")
        out = run_flux(["init"], self.repo)
        self.assertIn("check candidate", out.stdout)
        self.assertIn("run `flux check` once", out.stdout)
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            self.assertIn("verified = false", f.read())

    def test_detects_nx_before_package_json(self):
        self.write("nx.json", "{}")
        self.write("package.json", "{}")
        run_flux(["init"], self.repo)
        self.assertIn("nx run-many", self.candidate())

    def test_nx_candidate_is_never_scoped(self):
        """A gate whose meaning moves with the diff is not a gate."""
        self.write("nx.json", "{}")
        run_flux(["init"], self.repo)
        self.assertNotIn("affected", self.candidate())

    def test_no_rule_proposes_a_scoped_gate(self):
        """Sweep every marker in the table: none may yield a diff-scoped command."""
        scoped = ("affected", "--base=", "--changed", "--onlyChanged", "--since")
        support = {
            "package.json": '{"scripts": {"test": "jest"}}',
            "composer.json": '{"scripts": {"test": "phpunit"}}',
            "Rakefile": "",
        }
        for markers, _build in flux_module().CHECK_RULES:
            for marker in markers:
                if "*" in marker:
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True)
                    for name, body in support.items():
                        with open(os.path.join(tmp, name), "w") as f:
                            f.write(body)
                    with open(os.path.join(tmp, marker), "w") as f:
                        f.write(support.get(marker, "test:\n\techo hi\n"))
                    run_flux(["init"], tmp)
                    with open(os.path.join(tmp, ".flux", "flux.toml")) as f:
                        command = f.read()
                    for needle in scoped:
                        self.assertNotIn(needle, command, "%s -> %s" % (marker, command))

    def test_detects_bare_python_tests(self):
        """flux's own shape: a tests/ dir and no packaging metadata."""
        self.write("tests/test_thing.py", "")
        run_flux(["init"], self.repo)
        self.assertIn("python3 -m unittest discover -s tests", self.candidate())

    def test_test_dir_without_python_tests_falls_through(self):
        self.write("test/thing.spec.js", "")
        self.write("package.json", '{"scripts": {"test": "jest"}}')
        run_flux(["init"], self.repo)
        self.assertIn("npm run test", self.candidate())

    def test_detects_go(self):
        self.write("go.mod", "module x\n")
        run_flux(["init"], self.repo)
        self.assertIn("go test ./...", self.candidate())

    def test_detects_gradle_wrapper_before_bare_gradle(self):
        self.write("gradlew", "")
        self.write("build.gradle", "")
        run_flux(["init"], self.repo)
        self.assertIn("./gradlew check", self.candidate())

    def test_detects_dotnet_by_glob(self):
        self.write("App.csproj", "<Project/>")
        run_flux(["init"], self.repo)
        self.assertIn("dotnet test", self.candidate())

    def test_js_uses_the_lockfiles_package_manager(self):
        self.write("package.json", '{"scripts": {"test": "jest"}}')
        self.write("pnpm-lock.yaml", "")
        run_flux(["init"], self.repo)
        self.assertIn("pnpm run test", self.candidate())

    def test_js_prefers_an_explicit_check_script(self):
        self.write("package.json", '{"scripts": {"test": "jest", "check": "npm-run-all"}}')
        run_flux(["init"], self.repo)
        self.assertIn("npm run check", self.candidate())

    def test_js_pairs_lint_with_test(self):
        self.write("package.json", '{"scripts": {"test": "jest", "lint": "eslint ."}}')
        run_flux(["init"], self.repo)
        self.assertIn("npm run lint && npm run test", self.candidate())

    def test_scriptless_package_json_falls_through(self):
        """A manifest with no test script is not a gate — the next rule gets a turn."""
        self.write("package.json", '{"name": "x"}')
        self.write("Makefile", "check:\n\tpytest\n")
        run_flux(["init"], self.repo)
        self.assertIn("make check", self.candidate())

    def test_makefile_without_a_test_target_detects_nothing(self):
        self.write("Makefile", "build:\n\tcc main.c\n")
        out = run_flux(["init"], self.repo)
        self.assertIn("no gate detected", out.stdout)
        self.assertIn('command = ""', self.candidate())

    def test_justfile_uses_just(self):
        self.write("justfile", "test:\n\tcargo test\n")
        run_flux(["init"], self.repo)
        self.assertIn("just test", self.candidate())

    def test_no_detection_still_writes_config(self):
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("no gate detected", out.stdout)

    def test_refuses_overwrite_without_force(self):
        run_flux(["init"], self.repo)
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 1)
        self.assertIn("--force", out.stdout)
        self.assertEqual(run_flux(["init", "--force"], self.repo).returncode, 0)


class TestPrime(FluxRepoCase):
    def test_silent_noop_without_flux_dir(self):
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_emits_pack_with_state(self):
        run_flux(["init"], self.repo)
        run_flux(["state", "set", "phase", "P1", "next", "wire the thing"], self.repo)
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("flux prime", out.stdout)
        self.assertIn("@ main", out.stdout)
        self.assertIn("phase: P1", out.stdout)
        self.assertIn("next: wire the thing", out.stdout)

    def test_pack_respects_budget(self):
        run_flux(["init"], self.repo)
        # tiny budget: 10 tokens = 40 bytes
        toml = os.path.join(self.repo, ".flux", "flux.toml")
        with open(toml) as f:
            content = f.read().replace("budget_tokens = 2000", "budget_tokens = 10")
        with open(toml, "w") as f:
            f.write(content)
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertLessEqual(len(out.stdout.encode()), 40 + 1)  # + newline

    def test_flags_unverified_check(self):
        self.write("uv.lock", "")
        run_flux(["init"], self.repo)
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("[unverified — run it once]", out.stdout)

    def test_header_reports_ahead_of_default_branch(self):
        run_flux(["init"], self.repo)
        self._git("checkout", "-q", "-b", "feature")
        self._commit("one")
        self._commit("two")
        out = run_flux(["prime"], self.repo)
        self.assertIn("@ feature, 2 ahead of main", out.stdout.splitlines()[0])

    def test_header_reports_behind_default_branch(self):
        run_flux(["init"], self.repo)
        self._git("checkout", "-q", "-b", "feature")
        self._git("checkout", "-q", "main")
        self._commit("one")
        self._git("checkout", "-q", "feature")
        out = run_flux(["prime"], self.repo)
        self.assertIn("@ feature, 1 behind main", out.stdout.splitlines()[0])

    def test_header_stays_quiet_when_not_diverged(self):
        run_flux(["init"], self.repo)
        out = run_flux(["prime"], self.repo)
        header = out.stdout.splitlines()[0]
        self.assertIn("@ main", header)
        self.assertNotIn("ahead", header)
        self.assertNotIn("behind", header)

    def test_header_counts_dirty_files_in_singular(self):
        run_flux(["init"], self.repo)  # .flux/ is the one untracked entry
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("1 dirty file", header)
        self.assertNotIn("1 dirty files", header)
        self.write("scratch.txt", "x")
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("2 dirty files", header)

    def test_header_reports_default_branch_drift_even_with_upstream(self):
        """The regression this exists for: a pushed feature branch went silent."""
        run_flux(["init"], self.repo)
        self._with_remote()
        self._git("checkout", "-q", "-b", "feature")
        self._commit("one")
        self._commit("two")
        self._git("push", "-q", "-u", "origin", "feature")
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("@ feature, 2 ahead of origin/main", header)
        self.assertNotIn("unpushed", header)

    def test_header_separates_unpushed_from_default_branch_drift(self):
        run_flux(["init"], self.repo)
        self._with_remote()
        self._git("checkout", "-q", "-b", "feature")
        self._commit("one")
        self._commit("two")
        self._git("push", "-q", "-u", "origin", "feature")
        self._commit("three")  # local only
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("1 unpushed, 3 ahead of origin/main", header)

    def test_header_does_not_double_report_on_the_default_branch(self):
        run_flux(["init"], self.repo)
        self._with_remote()
        self._commit("one")
        self._commit("two")
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("2 unpushed", header)
        self.assertNotIn("ahead of", header)

    def test_header_reports_behind_own_upstream(self):
        run_flux(["init"], self.repo)
        self._with_remote()
        self._git("checkout", "-q", "-b", "feature")
        self._commit("one")
        self._git("push", "-q", "-u", "origin", "feature")
        self._git("reset", "-q", "--hard", "HEAD~1")
        header = run_flux(["prime"], self.repo).stdout.splitlines()[0]
        self.assertIn("1 behind origin/feature", header)

    def _with_remote(self):
        """A bare origin with main pushed — no origin/HEAD, as `git remote add` leaves it."""
        bare = os.path.join(self._tmp.name + "-origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
        self.addCleanup(shutil.rmtree, bare, True)
        self._git("remote", "add", "origin", bare)
        self._git("push", "-q", "-u", "origin", "main")

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo] + list(args), check=True)

    def _commit(self, message):
        self._git("-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-q", "--allow-empty", "-m", message)

    def test_never_fails(self):
        run_flux(["init"], self.repo)
        self.write(".flux/flux.toml", "[[[garbage")
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)


class TestState(FluxRepoCase):
    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)

    def test_set_and_get(self):
        self.assertEqual(run_flux(["state", "set", "phase", "P2"], self.repo).returncode, 0)
        out = run_flux(["state", "get", "phase"], self.repo)
        self.assertEqual(out.stdout.strip(), "P2")

    def test_get_all_lists_pairs(self):
        run_flux(["state", "set", "phase", "P2", "next", "n"], self.repo)
        out = run_flux(["state", "get"], self.repo)
        self.assertIn('phase = P2', out.stdout)
        self.assertIn("updated = ", out.stdout)

    def test_rejects_over_budget_write(self):
        out = run_flux(["state", "set", "notes", "x" * 9000], self.repo)
        self.assertEqual(out.returncode, 1)
        self.assertIn("refused", out.stderr)
        # and the old state survived untouched
        self.assertNotIn("xxxx", run_flux(["state", "get"], self.repo).stdout)

    def test_odd_args_usage_error(self):
        self.assertEqual(run_flux(["state", "set", "phase"], self.repo).returncode, 2)

    def test_a_flag_shaped_key_is_refused_not_written(self):
        """`set` takes bare key/value pairs, so `--phase` is always a typo. Writing it
        creates a second key beside the real one, reports success, and leaves prime
        rendering the stale value — silent corruption of the file that carries the
        project between sessions. Cost one session's state before this guard existed."""
        run_flux(["state", "set", "phase", "real"], self.repo)
        out = run_flux(["state", "set", "--phase", "typo"], self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertIn("looks like a flag", out.stderr)
        after = run_flux(["state", "get"], self.repo).stdout
        self.assertIn("phase = real", after)
        self.assertNotIn("--phase", after)

    def test_a_flag_shaped_key_anywhere_in_the_pairs_refuses_the_whole_write(self):
        out = run_flux(["state", "set", "phase", "P2", "--next", "n"], self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("P2", run_flux(["state", "get"], self.repo).stdout)

    def test_set_confirms_the_write_against_the_budget(self):
        # a silent write leaves no way to see how close the pack is to its cap.
        # The number is the RENDERED pack, not the log on disk: the budget prices
        # what reaches model context, and the log also carries superseded records.
        out = run_flux(["state", "set", "phase", "P2"], self.repo)
        self.assertRegex(out.stdout, r"flux state: wrote \d+ keys, (\d+)/8000 bytes")
        used = int(re.search(r"wrote \d+ keys, (\d+)/", out.stdout).group(1))
        flux = flux_module()
        rendered = flux.dump_flat_toml(flux.read_state(self.repo))
        self.assertEqual(used, len(rendered.encode("utf-8")))

    def test_the_budget_prices_the_pack_not_the_log(self):
        """Rewriting the same key ten times grows the log and not the pack. If the
        budget billed storage, an append-only format would strangle itself."""
        sizes = []
        for i in range(10):
            out = run_flux(["state", "set", "phase", "P%d" % i], self.repo)
            sizes.append(int(re.search(r"wrote \d+ keys, (\d+)/", out.stdout).group(1)))
        log = os.path.join(self.repo, ".flux", "state.jsonl")
        self.assertEqual(len(set(sizes)), 1)
        with open(log) as f:
            self.assertEqual(len(f.read().splitlines()), 10)
        self.assertGreater(os.path.getsize(log), sizes[0])


class TestStateLog(FluxRepoCase):
    """The append-only format. The merge tests are the point of the whole change:
    state.toml was rewritten whole every session, so every branch that held one
    diverged on the same five lines — which is why kiosk untracked it, and
    untracked state does not survive a clone."""

    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@t",
                        "-c", "user.name=t"] + list(args), check=True,
                       capture_output=True)

    def _commit_all(self, message):
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def _merge(self, ref):
        return subprocess.run(
            ["git", "-C", self.repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "merge", "--no-edit", ref], capture_output=True, text=True)

    def log_lines(self):
        with open(os.path.join(self.repo, ".flux", "state.jsonl")) as f:
            return [l for l in f.read().splitlines() if l.strip()]

    # --- replay -----------------------------------------------------------

    def test_last_write_wins_per_key(self):
        run_flux(["state", "set", "phase", "one"], self.repo)
        run_flux(["state", "set", "phase", "two"], self.repo)
        self.assertEqual(run_flux(["state", "get", "phase"], self.repo).stdout.strip(), "two")
        self.assertEqual(len(self.log_lines()), 2)  # the old value is still on disk

    def test_one_record_per_key_so_two_keys_are_independent(self):
        run_flux(["state", "set", "phase", "p", "next", "n"], self.repo)
        self.assertEqual(len(self.log_lines()), 2)

    def test_an_empty_value_clears_a_key(self):
        """The rewritten file had no way to remove a key but hand-editing it."""
        run_flux(["state", "set", "routing", "build"], self.repo)
        run_flux(["state", "set", "routing", ""], self.repo)
        self.assertNotIn("routing", run_flux(["state", "get"], self.repo).stdout)

    def test_updated_is_derived_and_cannot_be_set(self):
        """Stored, it was one guaranteed-divergent line per session on a file every
        branch rewrote — the conflict this format exists to remove."""
        run_flux(["state", "set", "phase", "p"], self.repo)
        self.assertIn("updated = ", run_flux(["state", "get"], self.repo).stdout)
        self.assertNotIn('"k": "updated"', "\n".join(self.log_lines()))
        out = run_flux(["state", "set", "updated", "whenever"], self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertIn("derived", out.stderr)

    def test_an_unreadable_line_is_skipped_not_raised(self):
        """A union merge can leave a line git could not join. prime must still
        render: this is the file that carries the project between sessions."""
        run_flux(["state", "set", "phase", "survives"], self.repo)
        path = os.path.join(self.repo, ".flux", "state.jsonl")
        with open(path, "a") as f:
            f.write("<<<<<<< HEAD\n{not json at all\n\n")
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("phase: survives", out.stdout)

    # --- the merge behaviour it was built for ------------------------------

    def test_two_branches_touching_different_keys_merge_clean(self):
        self._commit_all("adopt flux")
        self._git("checkout", "-q", "-b", "feature")
        run_flux(["state", "set", "phase", "on the feature"], self.repo)
        self._commit_all("feature session")
        self._git("checkout", "-q", "main")
        run_flux(["state", "set", "next", "on main"], self.repo)
        self._commit_all("main session")
        merged = self._merge("feature")
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        after = run_flux(["state", "get"], self.repo).stdout
        self.assertIn("phase = on the feature", after)
        self.assertIn("next = on main", after)

    def test_two_branches_touching_the_SAME_key_merge_clean_and_newer_wins(self):
        """union keeps both records rather than conflicting; replay picks the
        newer one. git never has to decide."""
        self._commit_all("adopt flux")
        self._git("checkout", "-q", "-b", "feature")
        run_flux(["state", "set", "phase", "older"], self.repo)
        self._commit_all("feature session")
        self._git("checkout", "-q", "main")
        time.sleep(0.01)
        run_flux(["state", "set", "phase", "newer"], self.repo)
        self._commit_all("main session")
        merged = self._merge("feature")
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        self.assertEqual(len(self.log_lines()), 2)  # both survive on disk
        self.assertEqual(
            run_flux(["state", "get", "phase"], self.repo).stdout.strip(), "newer")

    def test_the_old_format_is_what_conflicted(self):
        """The control. Same two sessions against a rewritten state.toml, which is
        what flux shipped until now — git cannot merge it."""
        self.write(".flux/state.toml", 'phase = "base"\nupdated = "1"\n')
        self._commit_all("legacy state")
        self._git("checkout", "-q", "-b", "feature")
        self.write(".flux/state.toml", 'phase = "on the feature"\nupdated = "2"\n')
        self._commit_all("feature session")
        self._git("checkout", "-q", "main")
        self.write(".flux/state.toml", 'phase = "base"\nnext = "on main"\nupdated = "3"\n')
        self._commit_all("main session")
        self.assertNotEqual(self._merge("feature").returncode, 0)

    # --- migration ---------------------------------------------------------

    def test_first_write_migrates_state_toml_and_removes_it(self):
        os.remove(os.path.join(self.repo, ".flux", "state.jsonl"))
        self.write(".flux/state.toml",
                   'phase = "carried"\nopen = "kept"\nupdated = "2026-01-01 00:00"\n')
        out = run_flux(["state", "set", "next", "fresh"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("migrated 2 keys", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".flux", "state.toml")))
        after = run_flux(["state", "get"], self.repo).stdout
        self.assertIn("phase = carried", after)
        self.assertIn("open = kept", after)
        self.assertIn("next = fresh", after)
        # the stale `updated` is not carried across — it is derived now
        self.assertNotIn("2026-01-01", after)

    def test_legacy_state_toml_still_renders_before_any_write(self):
        """Every adopting repo has one. prime must not go blank waiting for a set."""
        os.remove(os.path.join(self.repo, ".flux", "state.jsonl"))
        self.write(".flux/state.toml", 'phase = "legacy"\n')
        self.assertIn("phase: legacy", run_flux(["prime"], self.repo).stdout)

    # --- the cap on stored state ------------------------------------------

    def test_compact_collapses_to_one_record_per_live_key(self):
        for i in range(5):
            run_flux(["state", "set", "phase", "P%d" % i], self.repo)
        run_flux(["state", "set", "next", "n", "routing", "r"], self.repo)
        run_flux(["state", "set", "routing", ""], self.repo)
        before = run_flux(["state", "get"], self.repo).stdout
        out = run_flux(["state", "compact"], self.repo)
        self.assertIn("8 records -> 2", out.stdout)
        self.assertEqual(run_flux(["state", "get"], self.repo).stdout, before)

    def test_compaction_is_deterministic_so_two_clones_agree(self):
        run_flux(["state", "set", "next", "n", "phase", "p", "open", "o"], self.repo)
        run_flux(["state", "compact"], self.repo)
        once = self.log_lines()
        run_flux(["state", "compact"], self.repo)
        self.assertEqual(once, self.log_lines())

    def test_the_log_is_capped_in_code_and_compacts_itself(self):
        """CLAUDE.md: nothing flux stores as state may grow without a cap."""
        out = None
        for i in range(15):
            out = run_flux(["state", "set", "position", "x" * 7000], self.repo)
            if "compacted" in out.stdout:
                break
        self.assertIn("compacted", out.stdout)
        self.assertLessEqual(os.path.getsize(
            os.path.join(self.repo, ".flux", "state.jsonl")), 8000 * 8)
        self.assertIn("position = " + "x" * 7000,
                      run_flux(["state", "get"], self.repo).stdout)

    # --- history -----------------------------------------------------------

    def test_log_shows_the_superseded_value_a_rewrite_would_have_lost(self):
        run_flux(["state", "set", "phase", "the good one"], self.repo)
        run_flux(["state", "set", "phase", "the typo"], self.repo)
        out = run_flux(["state", "log"], self.repo)
        self.assertIn("the good one", out.stdout)
        self.assertLess(out.stdout.index("the typo"), out.stdout.index("the good one"))

    def test_log_is_capped_and_says_what_it_dropped(self):
        for i in range(6):
            run_flux(["state", "set", "phase", "P%d" % i], self.repo)
        out = run_flux(["state", "log", "2"], self.repo)
        self.assertEqual(len(out.stdout.splitlines()), 3)
        self.assertIn("+4 older", out.stdout)

    def test_log_clips_a_long_value(self):
        run_flux(["state", "set", "open", "y" * 500], self.repo)
        for line in run_flux(["state", "log"], self.repo).stdout.splitlines():
            self.assertLess(len(line), 200)


class TestCheck(FluxRepoCase):
    def configure(self, command, filt="failures", verified=None):
        run_flux(["init"], self.repo)
        stamp = "" if verified is None else "verified = %s\n" % ("true" if verified else "false")
        self.write(".flux/flux.toml",
                   '[check]\ncommand = "%s"\nfilter = "%s"\n%s[state]\nbudget_tokens = 2000\n'
                   % (command, filt, stamp))

    def read_toml(self):
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            return f.read()

    def test_pass_suppresses_output(self):
        self.configure("seq 5 9; true")
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("check passed", out.stdout)
        self.assertNotIn("7", out.stdout)  # command output suppressed (7 not in the command string)

    def test_fail_shows_failures_and_exit_code(self):
        self.configure("echo ok-noise; echo 'FAIL: test_x broke'; exit 3")
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 3)
        self.assertIn("FAIL: test_x broke", out.stdout)
        self.assertIn("check FAILED (exit 3)", out.stdout)

    def test_tail_filter(self):
        self.configure("seq 1 100; exit 1", filt="tail:5")
        out = run_flux(["check"], self.repo)
        lines = out.stdout.splitlines()
        self.assertIn("100", lines)
        self.assertNotIn("94", lines)

    def test_empty_command_errors(self):
        self.configure("")
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 1)
        self.assertIn("empty", out.stderr)

    def test_first_pass_flips_verified_stamp(self):
        self.configure("true", verified=False)
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("marked verified", out.stdout)
        self.assertIn("verified = true", self.read_toml())
        # second pass: stamp already flipped, no repeat note
        out2 = run_flux(["check"], self.repo)
        self.assertEqual(out2.returncode, 0)
        self.assertNotIn("marked verified", out2.stdout)

    def test_fail_keeps_stamp_and_warns_candidate(self):
        self.configure("exit 1", verified=False)
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 1)
        self.assertIn("never passed", out.stdout)
        self.assertIn("verified = false", self.read_toml())

    def test_legacy_config_without_stamp_untouched(self):
        self.configure("true")
        out = run_flux(["check"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertNotIn("verified", out.stdout)
        self.assertNotIn("verified", self.read_toml())


class TestHandoff(FluxRepoCase):
    def test_writes_capped_file(self):
        run_flux(["init"], self.repo)
        run_flux(["state", "set", "phase", "P3", "next", "verify handoff"], self.repo)
        out = run_flux(["handoff"], self.repo)
        self.assertEqual(out.returncode, 0)
        rel = out.stdout.strip()
        path = os.path.join(self.repo, rel) if not os.path.isabs(rel) else rel
        with open(path) as f:
            content = f.read()
        self.assertIn("phase: P3", content)
        self.assertIn("recent commits", content)
        self.assertLessEqual(len(content.encode()), 8000)

    def test_prime_points_at_latest_handoff(self):
        run_flux(["init"], self.repo)
        run_flux(["handoff"], self.repo)
        out = run_flux(["prime"], self.repo)
        self.assertIn("last handoff:", out.stdout)


class TestRun(FluxRepoCase):
    def test_dedupes_and_elides(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--tail", "10", "--", "sh", "-c",
                        "for i in $(seq 1 50); do echo spam; done; seq 1 200"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("[x50]", out.stdout)
        self.assertIn("lines elided", out.stdout)
        self.assertIn("200", out.stdout)  # tail survives

    def test_exit_code_passthrough(self):
        out = run_flux(["run", "--", "sh", "-c", "exit 7"], self.repo)
        self.assertEqual(out.returncode, 7)

    def test_works_without_flux_dir(self):
        out = run_flux(["run", "--", "echo", "hi"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("hi", out.stdout)

    NOISY_FAILURE = ("for i in $(seq 1 60); do echo noise$i; done; "
                     "echo 'FAIL: test_x broke'; "
                     "for i in $(seq 1 60); do echo more$i; done; exit 1")

    def test_filter_failures_keeps_failures_drops_noise(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--filter", "failures", "--", "sh", "-c", self.NOISY_FAILURE],
                       self.repo)
        self.assertEqual(out.returncode, 1)
        self.assertIn("FAIL: test_x broke", out.stdout)
        self.assertIn("noise60", out.stdout)       # context lines survive
        self.assertNotIn("noise1\n", out.stdout)   # the rest of the noise does not
        self.assertNotIn("more60", out.stdout)
        self.assertIn("filter=failures", out.stdout)

    def test_filter_failures_falls_back_to_tail_when_clean(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--filter", "failures", "--", "sh", "-c", "seq 1 200"], self.repo)
        self.assertEqual(out.returncode, 0)
        # check's no-match fallback: the last 40 lines, nothing before them
        self.assertTrue(out.stdout.startswith("161\n"), out.stdout[:80])
        self.assertIn("\n200\n", out.stdout)

    def test_filter_raw_keeps_everything(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--filter", "raw", "--", "sh", "-c", "seq 1 300"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("\n150\n", out.stdout)
        self.assertNotIn("elided", out.stdout)

    def test_filter_tail_n(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--filter", "tail:5", "--", "sh", "-c", "seq 1 200"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("200", out.stdout)
        self.assertNotIn("\n150\n", out.stdout)
        self.assertIn("filter=tail:5", out.stdout)

    def test_config_run_filter_is_the_default(self):
        run_flux(["init"], self.repo)
        self.write(".flux/flux.toml",
                   '[check]\ncommand = "true"\n[run]\nfilter = "failures"\n')
        out = run_flux(["run", "--", "sh", "-c", self.NOISY_FAILURE], self.repo)
        self.assertIn("FAIL: test_x broke", out.stdout)
        self.assertNotIn("more60", out.stdout)
        self.assertIn("filter=failures", out.stdout)

    def test_flag_beats_config_filter(self):
        run_flux(["init"], self.repo)
        self.write(".flux/flux.toml",
                   '[check]\ncommand = "true"\n[run]\nfilter = "failures"\n')
        out = run_flux(["run", "--filter", "raw", "--", "sh", "-c", self.NOISY_FAILURE], self.repo)
        self.assertIn("more60", out.stdout)

    def test_unknown_filter_flag_is_a_usage_error(self):
        run_flux(["init"], self.repo)
        out = run_flux(["run", "--filter", "bogus", "--", "echo", "hi"], self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertIn("unknown --filter", out.stderr)
        self.assertNotIn("hi", out.stdout)

    def test_unknown_config_filter_warns_and_elides(self):
        run_flux(["init"], self.repo)
        self.write(".flux/flux.toml",
                   '[check]\ncommand = "true"\n[run]\ntail = 10\nfilter = "bogus"\n')
        out = run_flux(["run", "--", "sh", "-c", "seq 1 200"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("ignoring unknown [run].filter", out.stderr)
        self.assertIn("lines elided", out.stdout)


class TestStateSourceDetection(FluxRepoCase):
    """`flux init --scan` inventories prior project state so /flux:adopt can migrate
    it. It must find things, size them, and read none of them."""

    def test_empty_repo_reports_nothing_found(self):
        out = run_flux(["init", "--scan"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("no prior project state", out.stdout)

    def test_finds_directory_and_file_sources(self):
        self.write(".paul/STATE.md", "x" * 3000)
        self.write(".paul/ROADMAP.md", "y" * 500)
        self.write("CLAUDE.md", "z" * 100)
        out = run_flux(["init", "--scan"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn(".paul", out.stdout)
        self.assertIn("2 files", out.stdout)
        self.assertIn("CLAUDE.md", out.stdout)
        # Largest prose file is named, so the skill knows where the knowledge is.
        self.assertIn("STATE.md", out.stdout)

    def test_scan_writes_nothing(self):
        self.write(".paul/STATE.md", "x" * 100)
        before = sorted(os.listdir(self.repo))
        out = run_flux(["init", "--scan"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(before, sorted(os.listdir(self.repo)))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".flux")))

    def test_scan_works_after_init(self):
        run_flux(["init"], self.repo)
        self.write(".paul/STATE.md", "x" * 100)
        out = run_flux(["init", "--scan"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn(".paul", out.stdout)

    def test_init_routes_to_adopt_when_prior_state_exists(self):
        self.write(".paul/STATE.md", "x" * 100)
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("/flux:adopt", out.stdout)
        self.assertIn(".paul", out.stdout)

    def test_init_stays_quiet_without_prior_state(self):
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertNotIn("/flux:adopt", out.stdout)

    def test_detection_reads_no_file_contents(self):
        # Unreadable content must not break the inventory: flux sizes, never opens.
        self.write(".paul/STATE.md", "x" * 50)
        path = os.path.join(self.repo, ".paul", "blob.bin")
        with open(path, "wb") as f:
            f.write(b"\x00\xff\xfe" * 100)
        out = run_flux(["init", "--scan"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("2 files", out.stdout)

    def test_assets_do_not_hide_the_prose(self):
        # A 3 MB mockup is the biggest file in a real .paul/ but carries no knowledge.
        self.write(".paul/STATE.md", "x" * 2000)
        with open(os.path.join(self.repo, ".paul", "mockup.jpg"), "wb") as f:
            f.write(b"\x00" * 50000)
        out = run_flux(["init", "--scan"], self.repo)
        self.assertIn("biggest: STATE.md", out.stdout)
        self.assertNotIn("mockup.jpg", out.stdout)

    def test_inventory_is_budget_capped(self):
        # The inventory lands in model context, so it obeys [state].budget_tokens
        # like everything else flux emits.
        self.write(".flux/flux.toml", '[check]\ncommand = "true"\n[state]\nbudget_tokens = 20\n')
        self.write("CLAUDE.md", "x" * 10000)
        out = run_flux(["init", "--scan"], self.repo)
        self.assertLessEqual(len(out.stdout.encode("utf-8")), 20 * 4 + 80)


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(REPO, "skills")
LIFECYCLE = ("plan", "audit", "apply", "wrap", "resume")
FLUX_SKILLS = LIFECYCLE + ("adopt",)

# A skill's whole file enters the context window when it is invoked, so leanness is a
# budget, not a preference. PAUL's equivalent five workflows totalled ~62 KB before the
# references they pulled in; the ceiling below keeps the distillation from creeping back.
SKILL_BUDGET_BYTES = 6000


def read_frontmatter(path):
    """Minimal YAML-ish frontmatter reader — enough for `key: value` skill headers."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return None, text
    fields = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields, text[end + 5:]


class TestLifecycleSkills(unittest.TestCase):
    """The five lifecycle skills are part of flux's contract with a session: they must
    exist, be user-invoked only, and stay inside the context budget."""

    def test_all_flux_skills_exist(self):
        for name in FLUX_SKILLS:
            self.assertTrue(
                os.path.isfile(os.path.join(SKILLS, name, "SKILL.md")),
                "missing flux skill: %s" % name)

    def test_frontmatter_is_wellformed(self):
        for name in FLUX_SKILLS:
            path = os.path.join(SKILLS, name, "SKILL.md")
            fields, body = read_frontmatter(path)
            self.assertIsNotNone(fields, "%s: no frontmatter block" % name)
            self.assertEqual(fields.get("name"), name,
                             "%s: frontmatter name must match its directory" % name)
            self.assertTrue(fields.get("description"), "%s: empty description" % name)
            self.assertTrue(body.strip(), "%s: no body" % name)

    def test_lifecycle_skills_are_not_model_invocable(self):
        # Lifecycle steps are ceremonies the user triggers; a model that invokes /wrap
        # on its own closes phases nobody asked to close.
        for name in FLUX_SKILLS:
            fields, _ = read_frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            self.assertEqual(fields.get("disable-model-invocation"), "true",
                             "%s: flux skills must be user-invoked only" % name)

    def test_each_skill_stays_within_budget(self):
        for name in FLUX_SKILLS:
            path = os.path.join(SKILLS, name, "SKILL.md")
            size = os.path.getsize(path)
            self.assertLessEqual(size, SKILL_BUDGET_BYTES,
                                 "%s: %d bytes exceeds the %d-byte skill budget"
                                 % (name, size, SKILL_BUDGET_BYTES))

    def test_apply_and_wrap_name_the_gate(self):
        # "Done" means the full configured gate passed. Both skills that can claim it
        # must point at `flux check`; apply must also name the scoped escape hatch it
        # iterates with, or sessions invent their own narrowing.
        for name in ("apply", "wrap"):
            _, body = read_frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            self.assertIn("flux check", body, "%s: must name the gate" % name)
        _, apply_body = read_frontmatter(os.path.join(SKILLS, "apply", "SKILL.md"))
        self.assertIn("flux run --filter failures", apply_body,
                      "apply: must name the scoped-iteration command")

    def test_no_skill_invokes_the_gate_with_arguments(self):
        # `flux check` is unmodifiable by decision: no args, no agent-side narrowing,
        # so that "check passed" always means the whole gate. A skill that documents
        # `flux check <target>` would teach sessions otherwise — and the CLI would
        # silently ignore the argument, which is worse.
        invocation = re.compile(r"`(flux check[^`]*)`|^\s*(flux check.*)$", re.M)
        for name in FLUX_SKILLS:
            _, body = read_frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            for match in invocation.finditer(body):
                call = (match.group(1) or match.group(2)).strip()
                self.assertEqual(call, "flux check",
                                 "%s: the gate takes no arguments, got %r" % (name, call))


class TestPluginManifest(unittest.TestCase):
    """The manifest is how flux reaches a session at all, and a manifest that fails to
    load is invisible — no skills, no hook, no error anywhere but `claude plugin list`.
    Both rules below cost a real outage on 2026-08-23."""

    def manifest(self):
        import json
        with open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_manifest_does_not_declare_the_standard_hooks_file(self):
        # Claude Code loads hooks/hooks.json automatically; naming it again in the
        # manifest is a duplicate-hooks load error that disables the whole plugin.
        # `hooks` may only point at *additional* files.
        hooks = self.manifest().get("hooks")
        self.assertTrue(
            hooks is None or "hooks/hooks.json" not in str(hooks),
            "plugin.json must not reference the auto-loaded hooks/hooks.json (got %r)" % (hooks,),
        )

    def test_standard_hooks_file_registers_prime(self):
        import json
        with open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8") as f:
            data = json.load(f)
        entries = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in entries for h in entry["hooks"]]
        self.assertTrue(any("flux" in c and "prime" in c for c in commands), commands)


class TestLog(FluxRepoCase):
    def _field_log(self):
        with open(os.path.join(self.repo, ".flux", flux_module().FIELD_LOG_NAME)) as f:
            return f.read()

    def test_appends_ordered_entries(self):
        run_flux(["init"], self.repo)
        self.assertEqual(
            run_flux(["log", "pack-miss", "prime lacked the gate cmd"], self.repo)
            .returncode, 0)
        self.assertEqual(
            run_flux(["log", "want", "a subset verb"], self.repo).returncode, 0)
        lines = [l for l in self._field_log().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("pack-miss  prime lacked the gate cmd", lines[0])
        self.assertIn("want  a subset verb", lines[1])  # newest last, first untouched

    def test_free_text_clipped_to_budget(self):
        run_flux(["init"], self.repo)
        toml = os.path.join(self.repo, ".flux", "flux.toml")
        with open(toml) as f:
            content = f.read().replace("budget_tokens = 2000", "budget_tokens = 10")
        with open(toml, "w") as f:
            f.write(content)
        run_flux(["log", "want", "x" * 500], self.repo)
        self.assertLessEqual(len(self._field_log().encode()), 40 + 80)  # 40B + prefix

    def test_missing_tag_or_text_errors_without_writing(self):
        run_flux(["init"], self.repo)
        for args in (["log"], ["log", "want"], ["log", "two words", "t"]):
            out = run_flux(args, self.repo)
            self.assertEqual(out.returncode, 2)
            self.assertIn("usage: flux log", out.stderr)
        self.assertEqual(self._field_log().strip(), "")  # nothing written

    def test_non_flux_repo_returns_2_and_writes_nothing(self):
        out = run_flux(["log", "want", "x"], self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".flux", flux_module().FIELD_LOG_NAME)))


class TestInitFieldLog(FluxRepoCase):
    def _path(self):
        return os.path.join(self.repo, ".flux", flux_module().FIELD_LOG_NAME)

    def test_init_creates_field_log(self):
        run_flux(["init"], self.repo)
        self.assertTrue(os.path.exists(self._path()))

    def test_force_preserves_existing_entries(self):
        run_flux(["init"], self.repo)
        run_flux(["log", "want", "keep me"], self.repo)
        with open(self._path()) as f:
            before = f.read()
        run_flux(["init", "--force"], self.repo)
        with open(self._path()) as f:
            self.assertEqual(f.read(), before)


class TestPackFooter(FluxRepoCase):
    def test_prime_ends_with_the_four_verbs(self):
        run_flux(["init"], self.repo)
        out = run_flux(["prime"], self.repo)
        footer = out.stdout.strip().splitlines()[-1]
        for verb in ("gate:", "subset:", "close:", "log:"):
            self.assertIn(verb, footer)
        for cmd in ("flux check", "flux run", "flux handoff", "flux log"):
            self.assertIn(cmd, footer)

    def test_footer_under_200_bytes(self):
        mod = flux_module()
        self.assertLessEqual(len(mod.PACK_FOOTER.encode()), mod.PACK_FOOTER_BUDGET)

    def test_non_flux_prime_still_silent(self):
        out = run_flux(["prime"], self.repo)
        self.assertEqual(out.stdout, "")


class TestHelp(unittest.TestCase):
    def test_no_args_prints_usage(self):
        out = subprocess.run([FLUX], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("flux", out.stdout)

    def test_unknown_command(self):
        out = subprocess.run([FLUX, "bogus"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


def _transcript(path, n, model="claude-opus-4-8"):
    """A synthetic transcript with n distinct main-thread assistant requests — the
    ledger's request definition (deduped on message.id, sidechain excluded)."""
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({
                "type": "assistant", "timestamp": "2026-08-21T09:00:00.000Z",
                "message": {"id": "m%d" % i, "model": model,
                            "usage": {"input_tokens": 1000,
                                      "cache_creation_input_tokens": 0,
                                      "cache_read_input_tokens": 1000,
                                      "output_tokens": 50},
                            "content": [{"type": "text", "text": "x"}]}}) + "\n")
    return path


class TestGuard(FluxRepoCase):
    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)

    def _hook(self, tpath, sid):
        return json.dumps({"transcript_path": tpath, "session_id": sid,
                           "hook_event_name": "UserPromptSubmit"})

    def _t(self, n, name="t.jsonl"):
        return _transcript(os.path.join(self.repo, name), n)

    def test_warns_at_threshold(self):
        out = run_flux(["guard"], self.repo, stdin=self._hook(self._t(130), "A"))
        self.assertEqual(out.returncode, 0)
        self.assertIn("130 requests", out.stdout)
        self.assertIn("Wrap now", out.stdout)

    def test_silent_under_threshold(self):
        out = run_flux(["guard"], self.repo, stdin=self._hook(self._t(100), "A"))
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_anti_nag_window_then_renudge(self):
        run_flux(["guard"], self.repo, stdin=self._hook(self._t(130), "A"))  # warns
        inside = run_flux(["guard"], self.repo, stdin=self._hook(self._t(145), "A"))
        self.assertEqual(inside.stdout, "")  # 130..130+25 is silent
        again = run_flux(["guard"], self.repo, stdin=self._hook(self._t(155), "A"))
        self.assertIn("155 requests", again.stdout)  # 130+25 reached

    def test_session_id_reset(self):
        run_flux(["guard"], self.repo, stdin=self._hook(self._t(130), "A"))  # warns
        fresh = run_flux(["guard"], self.repo, stdin=self._hook(self._t(130), "B"))
        self.assertIn("130 requests", fresh.stdout)  # a new session warns on its own

    def test_non_flux_repo_silent(self):
        shutil.rmtree(os.path.join(self.repo, ".flux"))
        out = run_flux(["guard"], self.repo, stdin=self._hook(self._t(130), "A"))
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_empty_stdin_silent(self):
        out = run_flux(["guard"], self.repo, stdin="")
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_missing_transcript_silent(self):
        j = json.dumps({"transcript_path": "/nonexistent/x.jsonl", "session_id": "A"})
        out = run_flux(["guard"], self.repo, stdin=j)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_never_returns_nonzero_on_garbage(self):
        out = run_flux(["guard"], self.repo, stdin="{not json")
        self.assertEqual(out.returncode, 0)


class TestKeyAge(FluxRepoCase):
    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)

    def _seed(self, pairs):
        """pairs: (key, value, days_ago) — write raw state-log records with a ts."""
        log = os.path.join(self.repo, ".flux", "state.jsonl")
        with open(log, "w") as f:
            for key, value, days in pairs:
                t = time.time() - days * 86400
                ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"
                f.write(json.dumps({"ts": ts, "k": key, "v": value}) + "\n")

    def test_stale_key_wears_age_fresh_does_not(self):
        self._seed([("open", "old blocker", 8), ("next", "today", 0)])
        out = run_flux(["prime"], self.repo).stdout
        lines = {ln.split(":")[0]: ln for ln in out.splitlines() if ":" in ln}
        self.assertIn("open: old blocker [8d]", out)
        self.assertIn("next: today", out)
        self.assertNotIn("next: today [", out)  # no suffix on a same-day key

    def test_within_stale_days_no_suffix(self):
        self._seed([("open", "recent", 1)])  # 1 <= stale_days default 2
        out = run_flux(["prime"], self.repo).stdout
        self.assertIn("open: recent", out)
        self.assertNotIn("[1d]", out)

    def test_header_and_positions_unmoved(self):
        self._seed([("phase", "P1", 8), ("next", "wire", 0)])
        out = run_flux(["prime"], self.repo).stdout
        self.assertIn("## flux prime", out.splitlines()[0])
        self.assertIn("phase: P1 [8d]", out)
        self.assertIn("next: wire", out)


class TestSeal(FluxRepoCase):
    def setUp(self):
        super().setUp()
        run_flux(["init"], self.repo)
        self.cache = os.path.join(self.repo, ".flux", "cache")
        os.makedirs(self.cache, exist_ok=True)

    def _prime_age(self, seconds):
        marker = os.path.join(self.cache, "last-prime")
        with open(marker, "w") as f:
            f.write("x")
        os.utime(marker, (time.time() - seconds, time.time() - seconds))

    def _wrap_at(self, iso):
        with open(os.path.join(self.cache, "last-wrap"), "w") as f:
            f.write(iso)

    def _rm_wrap(self):
        try:
            os.remove(os.path.join(self.cache, "last-wrap"))
        except OSError:
            pass

    def _seal(self, reason="clear"):
        return run_flux(["seal"], self.repo,
                        stdin=json.dumps({"reason": reason,
                                          "hook_event_name": "SessionEnd"}))

    def _marker(self):
        with open(os.path.join(self.cache, "last-session.json")) as f:
            return json.load(f)

    def _fieldlog(self):
        p = os.path.join(self.repo, ".flux", "field-log.md")
        return open(p).read() if os.path.exists(p) else ""

    def test_unwrapped_substantive_logs_and_warns(self):
        self._prime_age(1500)  # 25 min
        self._rm_wrap()
        out = self._seal()
        self.assertEqual(out.returncode, 0)
        self.assertTrue(self._marker()["warn"])
        self.assertIn("unwrapped", self._fieldlog())

    def test_wrapped_session_no_log_no_warn(self):
        self._prime_age(1500)
        self._wrap_at("2099-01-01T00:00:00.000Z")  # newer than last-prime
        before = self._fieldlog().count("unwrapped")
        self._seal()
        self.assertFalse(self._marker()["warn"])
        self.assertTrue(self._marker()["wrapped"])
        self.assertEqual(self._fieldlog().count("unwrapped"), before)

    def test_quick_session_no_warn(self):
        self._prime_age(30)  # under substantive_seconds (180)
        self._rm_wrap()
        before = self._fieldlog().count("unwrapped")
        self._seal()
        self.assertFalse(self._marker()["warn"])
        self.assertEqual(self._fieldlog().count("unwrapped"), before)

    def test_non_flux_repo_no_op(self):
        shutil.rmtree(os.path.join(self.repo, ".flux"))
        out = self._seal()
        self.assertEqual(out.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.cache, "last-session.json")))

    def test_empty_stdin_no_op(self):
        # no .flux/cache marker files; a flux repo but empty stdin still returns 0
        out = run_flux(["seal"], self.repo, stdin="")
        self.assertEqual(out.returncode, 0)

    def test_prime_warns_after_unwrapped(self):
        json.dump({"warn": True},
                  open(os.path.join(self.cache, "last-session.json"), "w"))
        out = run_flux(["prime"], self.repo).stdout
        self.assertIn("ended unwrapped", out)

    def test_prime_quiet_when_wrapped(self):
        json.dump({"warn": False},
                  open(os.path.join(self.cache, "last-session.json"), "w"))
        out = run_flux(["prime"], self.repo).stdout
        self.assertNotIn("ended unwrapped", out)

    def test_state_set_drops_wrap_breadcrumb(self):
        self._rm_wrap()
        run_flux(["state", "set", "next", "x"], self.repo)
        self.assertTrue(os.path.exists(os.path.join(self.cache, "last-wrap")))

    def test_handoff_drops_wrap_breadcrumb(self):
        self._rm_wrap()
        run_flux(["handoff"], self.repo)
        self.assertTrue(os.path.exists(os.path.join(self.cache, "last-wrap")))


class TestGuardHookWiring(unittest.TestCase):
    def test_hooks_json_registers_all_three_events(self):
        hooks_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "hooks", "hooks.json")
        with open(hooks_path) as f:
            data = json.load(f)
        for event in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
            self.assertIn(event, data["hooks"])
        cmds = [h["command"] for event in data["hooks"].values()
                for group in event for h in group["hooks"]]
        self.assertTrue(any(c.endswith("bin/flux\" guard") for c in cmds), cmds)
        self.assertTrue(any(c.endswith("bin/flux\" seal") for c in cmds), cmds)


class TestGuardTemplate(FluxRepoCase):
    def test_init_scaffolds_guard_block(self):
        run_flux(["init"], self.repo)
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            toml = f.read()
        self.assertIn("[guard]", toml)
        self.assertIn("warn_requests", toml)
        self.assertIn("substantive_seconds", toml)


if __name__ == "__main__":
    unittest.main()
