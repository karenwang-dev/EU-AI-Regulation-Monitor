import json
import shutil
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JS_FILE = PROJECT_ROOT / "app" / "web" / "static" / "js" / "timestamp_formatter.js"


NODE_TEST_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const jsFile = process.argv[process.argv.length - 1];
const code = fs.readFileSync(jsFile, "utf8");
const sandbox = { module: { exports: {} }, exports: {} };
sandbox.module.exports = sandbox.exports;
vm.runInNewContext(code, sandbox, { filename: jsFile });

const { parseTimestamp, formatTimestamp } = sandbox.module.exports;

const results = [];

function record(name, passed, detail) {
  results.push({ name, passed, detail });
}

const offsetParsed = parseTimestamp("2026-07-23T07:30:00+00:00");
record(
  "offset-aware parse",
  offsetParsed && offsetParsed.toISOString() === "2026-07-23T07:30:00.000Z",
  offsetParsed ? offsetParsed.toISOString() : null
);

const zParsed = parseTimestamp("2026-07-23T07:30:00Z");
record(
  "z-suffix parse",
  zParsed && zParsed.toISOString() === "2026-07-23T07:30:00.000Z",
  zParsed ? zParsed.toISOString() : null
);

const legacyParsed = parseTimestamp("2026-07-21T08:00:00");
record(
  "legacy naive parse as UTC",
  legacyParsed && legacyParsed.toISOString() === "2026-07-21T08:00:00.000Z",
  legacyParsed ? legacyParsed.toISOString() : null
);

record(
  "null fallback",
  formatTimestamp(null) === "—",
  formatTimestamp(null)
);

record(
  "empty fallback",
  formatTimestamp("") === "—",
  formatTimestamp("")
);

const berlinDisplay = formatTimestamp("2026-07-21T06:00:00+00:00", {
  timeZone: "Europe/Berlin",
  showTimezone: false,
});
record(
  "berlin conversion without abbreviation",
  berlinDisplay === "2026-07-21 08:00",
  berlinDisplay
);

const utcDisplay = formatTimestamp("2026-07-23T07:30:00+00:00", {
  timeZone: "UTC",
  showTimezone: false,
});
record(
  "utc display",
  utcDisplay === "2026-07-23 07:30",
  utcDisplay
);

console.log(JSON.stringify(results));
"""


@unittest.skipUnless(shutil.which("node"), "node is required for JS formatter tests")
class TimestampFormatterJsTests(unittest.TestCase):
    def test_js_formatter_cases(self):
        result = subprocess.run(
            ["node", "-e", NODE_TEST_SCRIPT, str(JS_FILE)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=PROJECT_ROOT,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            self.fail(
                "Node formatter test failed\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            )

        payload = json.loads(stdout)
        failures = [item for item in payload if not item["passed"]]
        if failures:
            self.fail(
                "Node formatter assertions failed:\n"
                + json.dumps(failures, indent=2)
            )


if __name__ == "__main__":
    unittest.main()
