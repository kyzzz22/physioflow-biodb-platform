import assert from "node:assert/strict";
import test from "node:test";
import { createDefaultContext, resolveConsoleContext } from "../src/lib/console-context.js";

test("default context uses the fallback participant and a one-hour window", () => {
  const now = new Date("2026-08-31T12:00:00.000Z");
  const context = createDefaultContext({}, "participant-01", now);
  assert.equal(context.participant, "participant-01");
  assert.equal(new Date(context.end) - new Date(context.start), 3600000);
  assert.equal(context.channels, "eda, ppg");
});

test("saved context takes precedence and request values are normalized", () => {
  const context = createDefaultContext(
    {
      experiment: " exp-a ",
      participant: " participant-02 ",
      start: "2026-08-31T10:00",
      end: "2026-08-31T11:00",
      channels: "eda, ppg, , eeg_alpha",
    },
    "participant-01"
  );
  const result = resolveConsoleContext(context);
  assert.equal(result.error, "");
  assert.equal(result.experiment, "exp-a");
  assert.equal(result.participant, "participant-02");
  assert.deepEqual(result.rows, ["eda", "ppg", "eeg_alpha"]);
});

test("invalid or reversed time ranges are rejected", () => {
  const base = { participant: "p", experiment: "", channels: "eda" };
  assert.match(resolveConsoleContext({ ...base, start: "", end: "" }).error, /時刻/);
  assert.match(
    resolveConsoleContext({ ...base, start: "2026-08-31T12:00", end: "2026-08-31T11:00" }).error,
    /終了時刻より前/
  );
});
