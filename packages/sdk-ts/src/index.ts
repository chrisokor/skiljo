export const SDK_VERSION = "0.1.0";

export { SkiljoClient, type ClientConfig } from "./client";
export { PoliciesResource, type Policy } from "./policies";
export { SkillsResource, type Skill, type SkillVersion } from "./skills";
export { JobsResource, type Job } from "./jobs";
export { SimulationsResource, type SimulationReport, type SimulationResponse } from "./simulations";
export {
  EvalRunsResource,
  type EvalRun,
  type EvalRunCreate,
  type EvalRunFilters,
} from "./eval-runs";
export {
  CrossDocumentResource,
  type CrossDocumentContradiction,
  type CrossDocumentCitation,
} from "./cross-document";

import { SkiljoClient, type ClientConfig } from "./client";
import { PoliciesResource } from "./policies";
import { SkillsResource } from "./skills";
import { JobsResource } from "./jobs";
import { SimulationsResource } from "./simulations";
import { EvalRunsResource } from "./eval-runs";
import { CrossDocumentResource } from "./cross-document";

export class Skiljo extends SkiljoClient {
  public policies: PoliciesResource;
  public skills: SkillsResource;
  public jobs: JobsResource;
  public simulations: SimulationsResource;
  public evalRuns: EvalRunsResource;
  public crossDocument: CrossDocumentResource;

  constructor(config: ClientConfig = {}) {
    super(config);
    this.policies = new PoliciesResource(this);
    this.skills = new SkillsResource(this);
    this.jobs = new JobsResource(this);
    this.simulations = new SimulationsResource(this);
    this.evalRuns = new EvalRunsResource(this);
    this.crossDocument = new CrossDocumentResource(this);
  }
}
