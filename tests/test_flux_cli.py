"""Tests for bin/flux. Stdlib only: python3 -m unittest discover -s tests"""

import importlib.machinery
import os
import re
import subprocess
import tempfile
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


def run_flux(args, cwd, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [FLUX] + args, cwd=cwd, capture_output=True, text=True, env=env, timeout=60
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
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".flux", "state.toml")))
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".flux", ".gitignore")))

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


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(REPO, "skills")
LIFECYCLE = ("plan", "audit", "apply", "wrap", "resume")

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

    def test_all_five_exist(self):
        for name in LIFECYCLE:
            self.assertTrue(
                os.path.isfile(os.path.join(SKILLS, name, "SKILL.md")),
                "missing lifecycle skill: %s" % name)

    def test_frontmatter_is_wellformed(self):
        for name in LIFECYCLE:
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
        for name in LIFECYCLE:
            fields, _ = read_frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            self.assertEqual(fields.get("disable-model-invocation"), "true",
                             "%s: lifecycle skills must be user-invoked only" % name)

    def test_each_skill_stays_within_budget(self):
        for name in LIFECYCLE:
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
        for name in LIFECYCLE:
            _, body = read_frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            for match in invocation.finditer(body):
                call = (match.group(1) or match.group(2)).strip()
                self.assertEqual(call, "flux check",
                                 "%s: the gate takes no arguments, got %r" % (name, call))


class TestHelp(unittest.TestCase):
    def test_no_args_prints_usage(self):
        out = subprocess.run([FLUX], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("flux", out.stdout)

    def test_unknown_command(self):
        out = subprocess.run([FLUX, "bogus"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
