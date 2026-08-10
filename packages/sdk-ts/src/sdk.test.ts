import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { Skiljo } from "./index";
import type { Policy } from "./policies";
import type { Skill, SkillVersion } from "./skills";
import type { Job } from "./jobs";
import type { SimulationReport, SimulationResponse } from "./simulations";
import type { EvalRun } from "./eval-runs";
import type { CrossDocumentContradiction } from "./cross-document";

function mockFetch(data: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValueOnce({
      ok,
      status,
      statusText: ok ? "OK" : "Error",
      json: async () => data,
    } as Response)
  );
}

describe("Skiljo top-level client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exposes policies, skills, jobs, simulations, evalRuns, and crossDocument resources", () => {
    const sdk = new Skiljo({ apiKey: "k" });
    expect(sdk.policies).toBeDefined();
    expect(sdk.skills).toBeDefined();
    expect(sdk.jobs).toBeDefined();
    expect(sdk.simulations).toBeDefined();
    expect(sdk.evalRuns).toBeDefined();
    expect(sdk.crossDocument).toBeDefined();
  });

  describe("policies.upload", () => {
    it("POSTs to /policies and returns Policy", async () => {
      const policy: Policy = {
        id: "p1",
        raw_text: "no refunds",
        uploaded_at: "2026-01-01T00:00:00Z",
      };
      mockFetch(policy);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.policies.upload("no refunds", "terms.txt");
      expect(result.id).toBe("p1");
      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/policies");
    });
  });

  describe("skills.extract", () => {
    it("POSTs to /skills/extract and returns job_id", async () => {
      mockFetch({ job_id: "j42" });

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.skills.extract("no refunds allowed", "refund_v1", "refund");
      expect(result.job_id).toBe("j42");

      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/skills/extract");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(init?.body as string);
      expect(body).toEqual({
        policy_text: "no refunds allowed",
        skill_name: "refund_v1",
        trigger: "refund",
      });
    });

    it("sends empty string trigger when omitted", async () => {
      mockFetch({ job_id: "j43" });

      const sdk = new Skiljo({ apiKey: "k" });
      await sdk.skills.extract("no refunds allowed", "refund_v1");

      const [, init] = vi.mocked(fetch).mock.calls[0];
      const body = JSON.parse(init?.body as string);
      expect(body.trigger).toBe("");
    });
  });

  describe("skills.get", () => {
    it("GETs /skills/{id} and returns Skill", async () => {
      const skill: Skill = {
        id: "s1",
        name: "refund_v1",
        created_at: "2026-01-01T00:00:00Z",
      };
      mockFetch(skill);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.skills.get("s1");
      expect(result.name).toBe("refund_v1");
    });
  });

  describe("skills.getVersions", () => {
    it("GETs /skills/{id}/versions and returns SkillVersion[]", async () => {
      const versions: SkillVersion[] = [
        {
          id: "v1",
          skill_id: "s1",
          version_number: 1,
          spec: {},
          status: "approved",
          created_at: "2026-01-01T00:00:00Z",
        },
      ];
      mockFetch(versions);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.skills.getVersions("s1");
      expect(result).toHaveLength(1);
      expect(result[0].version_number).toBe(1);
    });
  });

  describe("jobs.get", () => {
    it("GETs /jobs/{id} and returns Job", async () => {
      const job: Job = {
        id: "j1",
        kind: "extraction",
        status: "completed",
      };
      mockFetch(job);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.jobs.get("j1");
      expect(result.status).toBe("completed");
    });
  });

  describe("jobs.waitForCompletion", () => {
    it("polls until job is completed", async () => {
      const pendingJob: Job = { id: "j1", kind: "extraction", status: "pending" };
      const completedJob: Job = { id: "j1", kind: "extraction", status: "completed" };

      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValueOnce({
            ok: true,
            json: async () => pendingJob,
          } as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: async () => completedJob,
          } as Response)
      );

      // Speed up the polling interval using fake timers
      vi.useFakeTimers();

      const sdk = new Skiljo({ apiKey: "k" });
      const promise = sdk.jobs.waitForCompletion("j1");

      // Advance timers to bypass the 1s sleep between polls
      await vi.runAllTimersAsync();

      const result = await promise;
      expect(result.status).toBe("completed");

      vi.useRealTimers();
    });

    it("throws when timeout is exceeded", async () => {
      const pendingJob: Job = { id: "j2", kind: "extraction", status: "running" };

      // Always returns running — never completes
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => pendingJob,
        } as Response)
      );

      vi.useFakeTimers();

      const sdk = new Skiljo({ apiKey: "k" });
      const promise = sdk.jobs.waitForCompletion("j2", 2000);

      // Attach rejection handler BEFORE advancing timers to avoid unhandled rejection
      const assertion = expect(promise).rejects.toThrow("Job j2 timeout");

      await vi.runAllTimersAsync();

      await assertion;

      vi.useRealTimers();
    });
  });

  describe("simulations.create", () => {
    it("POSTs to /simulations and returns job_id", async () => {
      mockFetch({ job_id: "sim-job-1" });

      const sdk = new Skiljo({ apiKey: "k" });
      const tickets = [{ ticket_id: "t1", amount: 100 }];
      const result = await sdk.simulations.create("sv-uuid-1", tickets);
      expect(result.job_id).toBe("sim-job-1");

      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/simulations");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(init?.body as string);
      expect(body).toEqual({
        skill_version_id: "sv-uuid-1",
        tickets: [{ ticket_id: "t1", amount: 100 }],
      });
    });
  });

  describe("simulations.get", () => {
    it("GETs /simulations/{id} and returns SimulationResponse", async () => {
      const simulation: SimulationResponse = {
        id: "sim-1",
        status: "completed",
        summary: {
          match_rate: 0.95,
          escalation_accuracy: 0.92,
          automation_candidate_count: 10,
          results: [],
          contradictions: [],
        },
      };
      mockFetch(simulation);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.simulations.get("sim-1");
      expect(result.id).toBe("sim-1");
      expect(result.status).toBe("completed");
      expect(result.summary?.match_rate).toBe(0.95);

      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/simulations/sim-1");
    });
  });

  describe("simulations.getReport", () => {
    it("calls get and returns only the summary when completed", async () => {
      const simulation: SimulationResponse = {
        id: "sim-2",
        status: "completed",
        summary: {
          match_rate: 0.88,
          escalation_accuracy: 0.85,
          automation_candidate_count: 5,
          results: [],
        },
      };
      mockFetch(simulation);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.simulations.getReport("sim-2");
      expect(result.match_rate).toBe(0.88);
      expect(result.escalation_accuracy).toBe(0.85);
    });

    it("throws when summary is null", async () => {
      const simulation: SimulationResponse = {
        id: "sim-3",
        status: "running",
        summary: null,
      };
      mockFetch(simulation);

      const sdk = new Skiljo({ apiKey: "k" });
      await expect(sdk.simulations.getReport("sim-3")).rejects.toThrow(
        "Simulation sim-3 has no report yet (status: running)"
      );
    });
  });

  describe("evalRuns.create", () => {
    it("POSTs to /eval-runs and returns the created EvalRun", async () => {
      const run: EvalRun = {
        id: "run-1",
        commit_sha: "abc123",
        dataset_version: "v1",
        model: "claude-sonnet-4-6",
        metrics: { extraction_recall: 1.0 },
        ran_at: "2026-01-01T00:00:00Z",
      };
      mockFetch(run, true, 201);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.evalRuns.create({
        commit_sha: "abc123",
        dataset_version: "v1",
        model: "claude-sonnet-4-6",
        metrics: { extraction_recall: 1.0 },
      });

      expect(result.id).toBe("run-1");
      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/eval-runs");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(init?.body as string);
      expect(body).toEqual({
        commit_sha: "abc123",
        dataset_version: "v1",
        model: "claude-sonnet-4-6",
        metrics: { extraction_recall: 1.0 },
      });
    });
  });

  describe("evalRuns.list", () => {
    it("GETs /eval-runs with no query string when no filters given", async () => {
      mockFetch([]);

      const sdk = new Skiljo({ apiKey: "k" });
      await sdk.evalRuns.list();

      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/eval-runs");
      expect(String(url)).not.toContain("?");
    });

    it("GETs /eval-runs with model, commit_sha, and limit filters", async () => {
      const runs: EvalRun[] = [
        {
          id: "run-1",
          commit_sha: "abc123",
          dataset_version: "v1",
          model: "mockllm",
          metrics: { extraction_recall: 1.0 },
          ran_at: "2026-01-01T00:00:00Z",
        },
      ];
      mockFetch(runs);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.evalRuns.list({ model: "mockllm", commit_sha: "abc123", limit: 10 });

      expect(result).toHaveLength(1);
      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("model=mockllm");
      expect(String(url)).toContain("commit_sha=abc123");
      expect(String(url)).toContain("limit=10");
    });
  });

  describe("crossDocument.detect", () => {
    it("POSTs to /cross-document-contradictions and returns contradictions", async () => {
      const contradictions: CrossDocumentContradiction[] = [
        {
          decision_surface: "refund_eligibility",
          policy_1: "pol-1",
          policy_2: "pol-2",
          action_1: "deny",
          action_2: "approve",
          rationale: "Contradictory actions on the same decision surface",
          citation_1: { policy_id: "pol-1", zone: "deterministic", rule_index: 0, action: "deny" },
          citation_2: { policy_id: "pol-2", zone: "deterministic", rule_index: 1, action: "approve" },
        },
      ];
      mockFetch(contradictions);

      const sdk = new Skiljo({ apiKey: "k" });
      const result = await sdk.crossDocument.detect(["sv-1", "sv-2"]);

      expect(result).toHaveLength(1);
      expect(result[0].rationale).toBeDefined();
      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(String(url)).toContain("/cross-document-contradictions");
      expect(init?.method).toBe("POST");
      const body = JSON.parse(init?.body as string);
      expect(body).toEqual({ skill_version_ids: ["sv-1", "sv-2"] });
    });
  });
});
