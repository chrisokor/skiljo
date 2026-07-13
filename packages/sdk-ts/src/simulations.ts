import { SkiljoClient } from "./client";

export interface SimulationReport {
  match_rate: number;
  escalation_accuracy: number;
  automation_candidate_count: number;
  results: unknown[];
  contradictions?: unknown[];
}

export interface SimulationResponse {
  id: string;
  skill_id: string;
  batch_id: string;
  summary: SimulationReport;
  created_at: string;
}

export class SimulationsResource {
  constructor(private client: SkiljoClient) {}

  async create(skillId: string, batchId: string): Promise<{ job_id: string }> {
    return this.client.request<{ job_id: string }>(
      "POST",
      "/simulations",
      { skill_id: skillId, batch_id: batchId }
    );
  }

  async get(simId: string): Promise<SimulationResponse> {
    return this.client.request<SimulationResponse>(
      "GET",
      `/simulations/${simId}`
    );
  }

  async getReport(simId: string): Promise<SimulationReport> {
    const response = await this.get(simId);
    return response.summary;
  }
}
