import { SkiljoClient } from "./client";

export interface EvalRun {
  id: string;
  commit_sha: string;
  dataset_version: string;
  model: string;
  metrics: Record<string, number>;
  ran_at: string;
}

export interface EvalRunCreate {
  commit_sha: string;
  dataset_version: string;
  model: string;
  metrics: Record<string, number>;
}

export interface EvalRunFilters {
  model?: string;
  commit_sha?: string;
  limit?: number;
}

export class EvalRunsResource {
  constructor(private client: SkiljoClient) {}

  async create(run: EvalRunCreate): Promise<EvalRun> {
    return this.client.request<EvalRun>("POST", "/eval-runs", run);
  }

  async list(filters?: EvalRunFilters): Promise<EvalRun[]> {
    const params = new URLSearchParams();
    if (filters?.model) params.set("model", filters.model);
    if (filters?.commit_sha) params.set("commit_sha", filters.commit_sha);
    if (filters?.limit !== undefined) params.set("limit", String(filters.limit));

    const query = params.toString();
    return this.client.request<EvalRun[]>(
      "GET",
      query ? `/eval-runs?${query}` : "/eval-runs"
    );
  }
}
