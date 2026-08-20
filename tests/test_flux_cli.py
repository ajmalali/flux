"""Tests for bin/flux. Stdlib only: python3 -m unittest discover -s tests"""

import os
import subprocess
import tempfile
import unittest

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
        with open(os.path.join(self.repo, ".flux", "flux.toml")) as f:
            self.assertIn("nx affected", f.read())

    def test_no_detection_still_writes_config(self):
        out = run_flux(["init"], self.repo)
        self.assertEqual(out.returncode, 0)
        self.assertIn("no build system detected", out.stdout)

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
