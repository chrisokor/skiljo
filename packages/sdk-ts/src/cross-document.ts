import { SkiljoClient } from "./client";

export interface CrossDocumentCitation {
  policy_id: string;
  zone: string;
  rule_index: number;
  action: string;
}

export interface CrossDocumentContradiction {
  decision_surface: string;
  policy_1: string;
  policy_2: string;
  action_1: string;
  action_2: string;
  rationale: string;
  citation_1: CrossDocumentCitation;
  citation_2: CrossDocumentCitation;
}

export class CrossDocumentResource {
  constructor(private client: SkiljoClient) {}

  async detect(skillVersionIds: string[]): Promise<CrossDocumentContradiction[]> {
    return this.client.request<CrossDocumentContradiction[]>(
      "POST",
      "/cross-document-contradictions",
      { skill_version_ids: skillVersionIds }
    );
  }
}
