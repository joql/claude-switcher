"""Region adaptation uses isolated scripts and fake commands; no system changes."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT / 'core/claude-switch.sh').read_text()


class RegionTests(unittest.TestCase):
    def run_region(self, country):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = root / 'defaults-calls'
            functions = '\n'.join(
                re.search(rf'(?ms)^{name}\(\) \{{\n.*?^\}}', SOURCE).group()
                for name in ('locale_for', 'set_region')
            )
            script = root / 'switch.sh'
            script.write_text('COUNTRY_TARGET="US"\nLOCALE_TARGET="en_US"\n' + functions + r'''
curl() {
    case "$*" in
        *cloudflare*) printf 'loc=JP\n' ;;
        *) printf '{"country": "%s"}\n' "$TEST_COUNTRY" ;;
    esac
}
defaults() { printf '%s\n' "$*" >> "$TEST_CALLS"; }
osascript() { echo 'Unexpected administrator prompt' >&2; return 99; }
set_region
''')
            env = dict(os.environ, TEST_COUNTRY=country, TEST_CALLS=str(calls))
            result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
            return result, script.read_text(), calls.read_text() if calls.exists() else ''

    @unittest.skipUnless(os.uname().sysname == 'Darwin', 'Uses macOS sed syntax')
    def test_country_without_timezone_updates_region(self):
        result, script, calls = self.run_region('JP')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK:region=JP locale=ja_JP', result.stdout)
        self.assertIn('COUNTRY_TARGET="JP"', script)
        self.assertIn('LOCALE_TARGET="ja_JP"', script)
        self.assertEqual(calls, 'write -g AppleLocale ja_JP\n')

    def test_conflicting_countries_do_not_change_settings(self):
        result, script, calls = self.run_region('US')
        self.assertEqual(result.returncode, 1)
        self.assertIn('COUNTRY_TARGET="US"', script)
        self.assertEqual(calls, '')
