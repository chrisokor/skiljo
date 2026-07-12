import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { Skiljo } from "./index";
import type { Policy } from "./policies";
import type { Skill, SkillVersion } from "./skills";
import type { Job } from "./jobs";

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

  it("exposes policies, skills, and jobs resources", () => {
    const sdk = new Skiljo({ apiKey: "k" });
    expect(sdk.policies).toBeDefined();
    expect(sdk.skills).toBeDefined();
    expect(sdk.jobs).toBeDefined();
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
      const result = await sdk.skills.extract("p1", "refund_v1");
      expect(result.job_id).toBe("j42");
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
});
