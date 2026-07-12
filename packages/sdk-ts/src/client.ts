export interface ClientConfig {
  baseURL?: string;
  apiKey?: string;
}

export class SkiljoClient {
  public baseURL: string;
  public apiKey: string;

  constructor(config: ClientConfig = {}) {
    this.baseURL = config.baseURL || "http://localhost:8000";
    this.apiKey = config.apiKey || process.env.SKILJO_API_KEY || "";
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.baseURL}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
    };

    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json() as Promise<T>;
  }
}
