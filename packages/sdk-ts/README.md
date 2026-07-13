# Skiljo TypeScript SDK

Programmatic access to the Skiljo policy extraction and simulation engine.

Skiljo extracts refund, credit, and billing policies from documents into structured, versioned, executable "skill" specifications, then simulates those skills against ticket data to measure policy fidelity and detect contradictions between written policy and actual behavior.

## Installation

```bash
npm install @skiljo/sdk
# or
pnpm add @skiljo/sdk
# or
yarn add @skiljo/sdk
```

## Quick Start

```typescript
import { Skiljo } from "@skiljo/sdk";

const skiljo = new Skiljo({
  baseURL: "http://localhost:8000",
  apiKey: process.env.SKILJO_API_KEY,
});

// Upload a policy
const policy = await skiljo.policies.upload(policyText, "refund_policy.txt");
console.log(`Policy uploaded: ${policy.id}`);

// Extract a skill from the policy
const { job_id } = await skiljo.skills.extract(policy.id, "refund_policy_v1");
console.log(`Extraction started: ${job_id}`);

// Wait for extraction to complete
const job = await skiljo.jobs.waitForCompletion(job_id);
const skillId = job.result_ref;
console.log(`Skill extracted: ${skillId}`);
```

## Configuration

### Constructor

```typescript
const skiljo = new Skiljo({
  baseURL?: string;   // Default: "http://localhost:8000"
  apiKey?: string;    // Default: process.env.SKILJO_API_KEY
});
```

The client reads `apiKey` from the `SKILJO_API_KEY` environment variable if not explicitly provided.

```typescript
// Using environment variable
const skiljo = new Skiljo({
  baseURL: process.env.SKILJO_BASE_URL || "http://localhost:8000",
});

// Explicit configuration
const skiljo = new Skiljo({
  baseURL: "https://api.skiljo.com",
  apiKey: "sk_live_...",
});
```

## Usage Patterns

### Extracting a Policy

Extract a policy document into a structured skill specification:

```typescript
import { Skiljo } from "@skiljo/sdk";

const skiljo = new Skiljo();

// Step 1: Upload the policy document
const policyText = `
Refund Policy:
- Full refunds within 30 days of purchase
- 50% refund between 30-60 days
- No refunds after 60 days
- Damaged items eligible for full refund regardless of timeframe
- Exclusions: Final sale items, clearance items
`;

const policy = await skiljo.policies.upload(policyText, "refund_policy.txt");
console.log(`Uploaded policy: ${policy.id}`);
console.log(`Filename: ${policy.source_filename}`);

// Step 2: Start extraction job
const { job_id } = await skiljo.skills.extract(policy.id, "refund_policy_v1");
console.log(`Extraction job started: ${job_id}`);

// Step 3: Poll for completion
const extractionJob = await skiljo.jobs.waitForCompletion(job_id);

if (extractionJob.status === "completed") {
  const skillId = extractionJob.result_ref;
  console.log(`Extraction complete. Skill ID: ${skillId}`);
} else if (extractionJob.status === "failed") {
  console.error(`Extraction failed: ${extractionJob.error}`);
}
```

### Fetching an Extracted Skill

Retrieve an extracted skill specification and its version history:

```typescript
// Get skill metadata
const skill = await skiljo.skills.get(skillId);
console.log(`Skill: ${skill.name}`);
console.log(`Owner: ${skill.owner}`);
console.log(`Created: ${skill.created_at}`);
console.log(`Current version: ${skill.current_version_id}`);

// Get all versions of a skill
const versions = await skiljo.skills.getVersions(skillId);
console.log(`Total versions: ${versions.length}`);

versions.forEach((v) => {
  console.log(`
  Version ${v.version_number}:
  - ID: ${v.id}
  - Status: ${v.status}
  - Created: ${v.created_at}
  `);
});
```

### Running a Simulation

Simulate an extracted skill against a synthetic or imported batch of tickets:

```typescript
// Step 1: Create a simulation job
const { job_id } = await skiljo.simulations.create(skillId, "refund_v1");
console.log(`Simulation job started: ${job_id}`);

// Step 2: Wait for the simulation to complete
const simJob = await skiljo.jobs.waitForCompletion(job_id);

if (simJob.status === "completed") {
  const simId = simJob.result_ref;
  console.log(`Simulation complete. ID: ${simId}`);

  // Step 3: Fetch the full simulation response
  const sim = await skiljo.simulations.get(simId);
  console.log(`
Skill: ${sim.skill_id}
Batch: ${sim.batch_id}
Created: ${sim.created_at}
  `);

  // Step 4: Inspect the report
  const report = sim.summary;
  console.log(`
Match rate: ${(report.match_rate * 100).toFixed(1)}%
Escalation accuracy: ${(report.escalation_accuracy * 100).toFixed(1)}%
Automation candidates: ${report.automation_candidate_count}
Total results: ${report.results.length}
Contradictions detected: ${report.contradictions?.length || 0}
  `);
} else if (simJob.status === "failed") {
  console.error(`Simulation failed: ${simJob.error}`);
}
```

### Extracting and Simulating (Full Workflow)

A complete end-to-end example:

```typescript
import { Skiljo } from "@skiljo/sdk";

async function runFullWorkflow() {
  const skiljo = new Skiljo({
    baseURL: "http://localhost:8000",
    apiKey: process.env.SKILJO_API_KEY,
  });

  // Upload policy
  console.log("Uploading policy...");
  const policy = await skiljo.policies.upload(
    `
Refund Policy:
- Refunds within 30 days: full refund
- Refunds after 30 days: 50% refund
- Damaged items: full refund any time
    `,
    "company_refund_policy.txt"
  );
  console.log(`Policy uploaded: ${policy.id}`);

  // Extract skill
  console.log("Extracting skill...");
  const { job_id: extractJobId } = await skiljo.skills.extract(
    policy.id,
    "refund_policy_v1"
  );
  const extractJob = await skiljo.jobs.waitForCompletion(extractJobId);

  if (extractJob.status !== "completed") {
    throw new Error(`Extraction failed: ${extractJob.error}`);
  }

  const skillId = extractJob.result_ref!;
  console.log(`Skill extracted: ${skillId}`);

  // Verify skill
  const skill = await skiljo.skills.get(skillId);
  console.log(`Skill name: ${skill.name}`);

  // Run simulation
  console.log("Running simulation...");
  const { job_id: simJobId } = await skiljo.simulations.create(
    skillId,
    "refund_v1"
  );
  const simJob = await skiljo.jobs.waitForCompletion(simJobId);

  if (simJob.status !== "completed") {
    throw new Error(`Simulation failed: ${simJob.error}`);
  }

  const simId = simJob.result_ref!;
  console.log(`Simulation complete: ${simId}`);

  // Fetch results
  const simulation = await skiljo.simulations.get(simId);
  const report = simulation.summary;

  console.log(`
=== Simulation Report ===
Match rate: ${(report.match_rate * 100).toFixed(1)}%
Escalation accuracy: ${(report.escalation_accuracy * 100).toFixed(1)}%
Automation candidates: ${report.automation_candidate_count}
Results analyzed: ${report.results.length}
Contradictions detected: ${report.contradictions?.length || 0}
  `);

  return { skillId, simId, report };
}

// Run the workflow
runFullWorkflow().catch(console.error);
```

## API Reference

### Skiljo

The main client class. Extends `SkiljoClient` and exposes resource interfaces.

#### Constructor

```typescript
new Skiljo(config?: ClientConfig)
```

**Parameters:**
- `config.baseURL?: string` — API base URL (default: `http://localhost:8000`)
- `config.apiKey?: string` — Bearer token for authentication (default: `process.env.SKILJO_API_KEY`)

**Properties:**
- `policies: PoliciesResource` — Policy upload and management
- `skills: SkillsResource` — Skill extraction and retrieval
- `jobs: JobsResource` — Job status polling
- `simulations: SimulationsResource` — Simulation creation and reporting

#### Example

```typescript
const skiljo = new Skiljo({
  baseURL: "https://api.skiljo.com",
  apiKey: "sk_live_...",
});
```

### PoliciesResource

Upload and manage policy documents.

#### `upload(rawText: string, filename?: string): Promise<Policy>`

Upload a policy document for extraction.

**Parameters:**
- `rawText: string` — The policy document text
- `filename?: string` — Optional filename for reference

**Returns:** `Policy` object with ID and metadata

**Example:**
```typescript
const policy = await skiljo.policies.upload(
  "Refund Policy: ...",
  "policy.txt"
);
console.log(policy.id);      // "policy_123..."
console.log(policy.raw_text); // "Refund Policy: ..."
console.log(policy.uploaded_at);
```

### SkillsResource

Extract and retrieve skill specifications.

#### `extract(policyId: string, skillName: string): Promise<{ job_id: string }>`

Start an extraction job to convert a policy into a skill specification.

**Parameters:**
- `policyId: string` — ID of the policy to extract (from `policies.upload()`)
- `skillName: string` — Name for the extracted skill (e.g., `"refund_policy_v1"`)

**Returns:** Object with `job_id` for polling

**Example:**
```typescript
const { job_id } = await skiljo.skills.extract(policyId, "refund_policy_v1");
const job = await skiljo.jobs.waitForCompletion(job_id);
```

#### `get(skillId: string): Promise<Skill>`

Retrieve a skill by ID.

**Parameters:**
- `skillId: string` — The skill ID

**Returns:** `Skill` object with metadata

**Example:**
```typescript
const skill = await skiljo.skills.get(skillId);
console.log(skill.name);
console.log(skill.owner);
console.log(skill.created_at);
```

#### `getVersions(skillId: string): Promise<SkillVersion[]>`

Get all versions of a skill.

**Parameters:**
- `skillId: string` — The skill ID

**Returns:** Array of `SkillVersion` objects

**Example:**
```typescript
const versions = await skiljo.skills.getVersions(skillId);
versions.forEach((v) => {
  console.log(`Version ${v.version_number}: ${v.status}`);
});
```

### JobsResource

Poll background job status.

#### `get(jobId: string): Promise<Job>`

Get the current status of a job.

**Parameters:**
- `jobId: string` — The job ID (returned from extraction or simulation start)

**Returns:** `Job` object with status and results

**Example:**
```typescript
const job = await skiljo.jobs.get(jobId);
if (job.status === "completed") {
  const resultId = job.result_ref;
  console.log(`Result: ${resultId}`);
} else if (job.status === "failed") {
  console.error(`Error: ${job.error}`);
}
```

#### `waitForCompletion(jobId: string, timeoutMs?: number): Promise<Job>`

Poll a job until completion or timeout.

Polls every 1 second by default. Useful for synchronous workflows without manual polling.

**Parameters:**
- `jobId: string` — The job ID
- `timeoutMs?: number` — Timeout in milliseconds (default: 300000 = 5 minutes)

**Returns:** `Job` object when completed or failed

**Throws:** Error if job times out

**Example:**
```typescript
try {
  const job = await skiljo.jobs.waitForCompletion(jobId);
  console.log(job.status); // "completed" or "failed"
} catch (err) {
  console.error("Job timed out");
}
```

### SimulationsResource

Run simulations and fetch reports.

#### `create(skillId: string, batchId: string): Promise<{ job_id: string }>`

Start a simulation job to evaluate a skill against a batch of tickets.

**Parameters:**
- `skillId: string` — The skill ID (from extraction)
- `batchId: string` — The ticket batch ID (e.g., `"refund_v1"`)

**Returns:** Object with `job_id` for polling

**Example:**
```typescript
const { job_id } = await skiljo.simulations.create(skillId, "refund_v1");
const job = await skiljo.jobs.waitForCompletion(job_id);
```

#### `get(simId: string): Promise<SimulationResponse>`

Retrieve a completed simulation with full metadata and report.

**Parameters:**
- `simId: string` — The simulation ID (from job `result_ref`)

**Returns:** `SimulationResponse` with summary, metadata, and results

**Example:**
```typescript
const sim = await skiljo.simulations.get(simId);
console.log(sim.id);
console.log(sim.skill_id);
console.log(sim.batch_id);
console.log(sim.summary.match_rate);
```

#### `getReport(simId: string): Promise<SimulationReport>`

Retrieve just the report from a simulation (convenience method).

**Parameters:**
- `simId: string` — The simulation ID

**Returns:** `SimulationReport` with metrics and results

**Example:**
```typescript
const report = await skiljo.simulations.getReport(simId);
console.log(`Match rate: ${report.match_rate}`);
console.log(`Accuracy: ${report.escalation_accuracy}`);
console.log(`Contradictions: ${report.contradictions?.length || 0}`);
```

## Type Definitions

### Policy

```typescript
interface Policy {
  id: string;                    // Unique policy identifier
  source_filename?: string;      // Original filename if provided
  raw_text: string;             // The policy document text
  uploaded_at: string;          // ISO timestamp
}
```

### Skill

```typescript
interface Skill {
  id: string;                   // Unique skill identifier
  name: string;                 // Skill name (e.g., "refund_policy_v1")
  owner?: string;               // User who created it
  created_at: string;           // ISO timestamp
  current_version_id?: string;  // ID of the latest version
}
```

### SkillVersion

```typescript
interface SkillVersion {
  id: string;                   // Unique version identifier
  skill_id: string;             // Parent skill ID
  version_number: number;       // Sequential version number
  spec: unknown;                // The structured skill specification (JSON)
  status: "draft" | "approved"; // Approval status
  created_at: string;           // ISO timestamp
}
```

### Job

```typescript
interface Job {
  id: string;                              // Unique job identifier
  kind: string;                            // Job type (e.g., "extract", "simulate")
  status: "pending" | "running" | "completed" | "failed";
  payload?: unknown;                       // Input payload
  result_ref?: string;                     // ID of the result (skill_id or sim_id)
  error?: string;                          // Error message if failed
  started_at?: string;                     // ISO timestamp
  completed_at?: string;                   // ISO timestamp
}
```

### SimulationReport

```typescript
interface SimulationReport {
  match_rate: number;                      // 0-1, fraction of decisions matching expected outcomes
  escalation_accuracy: number;             // 0-1, accuracy of escalation detection
  automation_candidate_count: number;      // Number of decisions that could be automated
  results: unknown[];                      // Per-ticket simulation results
  contradictions?: unknown[];              // Detected policy contradictions
}
```

### SimulationResponse

```typescript
interface SimulationResponse {
  id: string;                              // Unique simulation run identifier
  skill_id: string;                        // The skill being evaluated
  batch_id: string;                        // The ticket batch used
  summary: SimulationReport;               // The simulation report
  created_at: string;                      // ISO timestamp
}
```

## Error Handling

All SDK methods throw errors on HTTP failures. Errors include HTTP status and status text.

```typescript
try {
  const policy = await skiljo.policies.upload(policyText);
} catch (err: unknown) {
  if (err instanceof Error) {
    console.error(`API error: ${err.message}`);
    // Output: "API error: HTTP 401: Unauthorized"
  }
}
```

Common error codes:
- `400` — Bad request (invalid input)
- `401` — Unauthorized (missing or invalid API key)
- `404` — Not found (resource doesn't exist)
- `500` — Server error

## Authentication

The SDK uses Bearer token authentication via the `Authorization` header.

```typescript
// Authenticate with environment variable
const skiljo = new Skiljo();  // reads SKILJO_API_KEY

// Or provide explicit key
const skiljo = new Skiljo({
  apiKey: "sk_live_abcdefg123...",
});
```

The API key is passed to every request. Ensure your API key is kept secret.

```typescript
// ❌ DON'T: hardcode in source code
const skiljo = new Skiljo({ apiKey: "sk_live_123..." });

// ✅ DO: load from environment
const skiljo = new Skiljo({
  apiKey: process.env.SKILJO_API_KEY,
});
```

## Timeouts

By default, `waitForCompletion()` waits up to 5 minutes (300,000 ms). Customize via the `timeoutMs` parameter:

```typescript
// Wait up to 10 minutes
const job = await skiljo.jobs.waitForCompletion(jobId, 600000);

// Wait only 30 seconds
const job = await skiljo.jobs.waitForCompletion(jobId, 30000);
```

For longer-running operations or external polling, use `jobs.get()` directly:

```typescript
let job = await skiljo.jobs.get(jobId);
while (job.status === "pending" || job.status === "running") {
  await new Promise((r) => setTimeout(r, 2000)); // 2 second delay
  job = await skiljo.jobs.get(jobId);
}
```

## Testing

The SDK is fully typed and works with Node.js 18+. For testing, you can mock the HTTP client or use a local Skiljo instance.

```typescript
import { describe, it, expect } from "vitest";
import { Skiljo } from "@skiljo/sdk";

describe("Skiljo SDK", () => {
  it("should initialize with default config", () => {
    const skiljo = new Skiljo();
    expect(skiljo.baseURL).toBe("http://localhost:8000");
  });

  it("should accept custom config", () => {
    const skiljo = new Skiljo({
      baseURL: "https://api.example.com",
      apiKey: "test-key",
    });
    expect(skiljo.baseURL).toBe("https://api.example.com");
    expect(skiljo.apiKey).toBe("test-key");
  });
});
```

## Developing the SDK

```bash
# Install dependencies
pnpm install

# Build
pnpm build

# Run tests
pnpm test

# Watch mode (development)
pnpm test --watch
```

The SDK uses tsup for bundling, producing both ESM and CommonJS outputs with full TypeScript definitions.

## License

MIT
