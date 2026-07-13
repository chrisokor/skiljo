import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { Skiljo } from "./index";
import type { Policy } from "./policies";
import type { Skill, SkillVersion } from "./skills";
import type { Job } from "./jobs";
import type { SimulationReport, SimulationResponse } from "./simulations";

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

  it("exposes policies, skills, jobs, and simulations resources", () => {
    const sdk = new Skiljo({ apiKey: "k" });
    expect(sdk.policies).toBeDefined();
    expect(sdk.skills).toBeDefined();
    expect(sdk.jobs).toBeDefined();
    expect(sdk.simulations).toBeDefined();
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
});
