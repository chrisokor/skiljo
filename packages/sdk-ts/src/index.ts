export const SDK_VERSION = "0.1.0";

export { SkiljoClient, type ClientConfig } from "./client";
export { PoliciesResource, type Policy } from "./policies";
export { SkillsResource, type Skill, type SkillVersion } from "./skills";
export { JobsResource, type Job } from "./jobs";

import { SkiljoClient, type ClientConfig } from "./client";
import { PoliciesResource } from "./policies";
import { SkillsResource } from "./skills";
import { JobsResource } from "./jobs";

export class Skiljo extends SkiljoClient {
  public policies: PoliciesResource;
  public skills: SkillsResource;
  public jobs: JobsResource;

  constructor(config: ClientConfig = {}) {
    super(config);
    this.policies = new PoliciesResource(this);
    this.skills = new SkillsResource(this);
    this.jobs = new JobsResource(this);
  }
}
