/**
 * Job Runner - delta-notifier bridge
 *
 * Listens for delta notifications about new ValidationJob triples with
 * status=pending, then triggers the Python validation service.
 */

import express from "express";
import fetch from "node-fetch";

const app = express();
app.use(express.json({ limit: "10mb" }));

const VALIDATION_SERVICE_URL = process.env.VALIDATION_SERVICE_URL || "http://validation";
const EXT_STATUS = "http://mu.semte.ch/vocabularies/ext/status";

app.post("/delta", async (req, res) => {
  // Respond immediately so delta-notifier doesn't time out
  res.status(202).send();

  const changesets = Array.isArray(req.body) ? req.body : [];
  const inserts = changesets.flatMap((c) => c.inserts || []);

  // Find subjects that were just assigned status=pending
  const pendingJobUris = inserts
    .filter(
      (triple) =>
        triple.predicate?.value === EXT_STATUS &&
        triple.object?.value === "pending"
    )
    .map((triple) => triple.subject.value);

  for (const jobUri of pendingJobUris) {
    console.log(`[job-runner] Triggering validation for job: ${jobUri}`);
    try {
      const response = await fetch(`${VALIDATION_SERVICE_URL}/run-job`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_uri: jobUri }),
      });
      if (!response.ok) {
        const text = await response.text();
        console.error(`[job-runner] Validation service error ${response.status}: ${text}`);
      } else {
        console.log(`[job-runner] Job accepted: ${jobUri}`);
      }
    } catch (err) {
      console.error(`[job-runner] Failed to trigger job ${jobUri}:`, err.message);
    }
  }
});

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

const PORT = process.env.PORT || 80;
app.listen(PORT, () => {
  console.log(`[job-runner] Listening on :${PORT}`);
});
