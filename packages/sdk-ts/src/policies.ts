import { SkiljoClient } from "./client";

export interface Policy {
  id: string;
  source_filename?: string;
  raw_text: string;
  uploaded_at: string;
}

export class PoliciesResource {
  constructor(private client: SkiljoClient) {}

  async upload(rawText: string, filename?: string): Promise<Policy> {
    return this.client.request<Policy>("POST", "/policies", {
      raw_text: rawText,
      source_filename: filename,
    });
  }
}
