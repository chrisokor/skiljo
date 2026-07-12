import { SkiljoClient } from "./client";

export interface Skill {
  id: string;
  name: string;
  owner?: string;
  created_at: string;
  current_version_id?: string;
}

export interface SkillVersion {
  id: string;
  skill_id: string;
  version_number: number;
  spec: unknown;
  status: "draft" | "approved";
  created_at: string;
}

export class SkillsResource {
  constructor(private client: SkiljoClient) {}

  async extract(
    policyId: string,
    skillName: string
  ): Promise<{ job_id: string }> {
    return this.client.request<{ job_id: string }>(
      "POST",
      "/skills/extract",
      { policy_id: policyId, skill_name: skillName }
    );
  }

  async get(skillId: string): Promise<Skill> {
    return this.client.request<Skill>("GET", `/skills/${skillId}`);
  }

  async getVersions(skillId: string): Promise<SkillVersion[]> {
    return this.client.request<SkillVersion[]>(
      "GET",
      `/skills/${skillId}/versions`
    );
  }
}
