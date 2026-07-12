import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { SkiljoClient, type ClientConfig } from "./client";

describe("SkiljoClient", () => {
  describe("constructor defaults", () => {
    it("uses localhost:8000 as default baseURL", () => {
      const client = new SkiljoClient();
      expect(client.baseURL).toBe("http://localhost:8000");
    });

    it("uses SKILJO_API_KEY env var as default apiKey", () => {
      const original = process.env.SKILJO_API_KEY;
      process.env.SKILJO_API_KEY = "env-key-123";
      const client = new SkiljoClient();
      expect(client.apiKey).toBe("env-key-123");
      process.env.SKILJO_API_KEY = original;
    });

    it("prefers explicit config over env var", () => {
      process.env.SKILJO_API_KEY = "env-key";
      const client = new SkiljoClient({ apiKey: "explicit-key" });
      expect(client.apiKey).toBe("explicit-key");
      delete process.env.SKILJO_API_KEY;
    });

    it("accepts custom baseURL", () => {
      const client = new SkiljoClient({ baseURL: "https://api.example.com" });
      expect(client.baseURL).toBe("https://api.example.com");
    });
  });

  describe("request method sends Bearer auth header", () => {
    beforeEach(() => {
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("sets Authorization: Bearer header on every request", async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "abc" }),
      } as Response);

      const client = new SkiljoClient({ apiKey: "test-key" });
      // Cast to any to call protected method in test
      await client.request("GET", "/health");

      expect(mockFetch).toHaveBeenCalledOnce();
      const [, init] = mockFetch.mock.calls[0];
      const headers = init?.headers as Record<string, string>;
      expect(headers["Authorization"]).toBe("Bearer test-key");
    });

    it("throws on non-ok response", async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
      } as Response);

      const client = new SkiljoClient({ apiKey: "bad-key" });
      await expect(client.request("GET", "/health")).rejects.toThrow(
        "HTTP 401"
      );
    });

    it("sends JSON body for POST requests", async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ job_id: "j1" }),
      } as Response);

      const client = new SkiljoClient({ apiKey: "k" });
      await client.request("POST", "/policies", { raw_text: "hi" });

      const [, init] = mockFetch.mock.calls[0];
      expect(init?.body).toBe(JSON.stringify({ raw_text: "hi" }));
    });
  });
});
