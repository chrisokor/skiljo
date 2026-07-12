import { SkiljoClient } from "./client";

export interface Job {
  id: string;
  kind: string;
  status: "pending" | "running" | "completed" | "failed";
  payload?: unknown;
  result_ref?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export class JobsResource {
  constructor(private client: SkiljoClient) {}

  async get(jobId: string): Promise<Job> {
    return this.client.request<Job>("GET", `/jobs/${jobId}`);
  }

  async waitForCompletion(
    jobId: string,
    timeoutMs: number = 300000
  ): Promise<Job> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const job = await this.get(jobId);
      if (job.status === "completed" || job.status === "failed") {
        return job;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }

    throw new Error(`Job ${jobId} timeout`);
  }
}
