import { describe, expect, it } from "vitest";
import { skillSchema, ticketSchema } from "./types";

describe("generated zod schemas", () => {
  it("parses a valid skill", () => {
    const skill = skillSchema.parse({
      skill_name: "process_refund_request",
      version: 1,
      trigger: "customer_requests_refund",
      inputs: [{ name: "refund_amount", type: "number" }],
      decision_zones: {
        deterministic: [
          { condition: { all: [{ field: "purchase_days_ago", op: "lte", value: 30 }] }, action: "approve_refund" },
        ],
        llm_assisted: [],
        human_only: [],
      },
    });
    expect(skill.skill_name).toBe("process_refund_request");
  });

  it("parses a valid ticket", () => {
    const ticket = ticketSchema.parse({
      ticket_id: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      refund_amount: 42.5,
      purchase_days_ago: 10,
      ground_truth_decision: "approve",
    });
    expect(ticket.refund_amount).toBe(42.5);
  });
});
