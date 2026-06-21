import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import $RefParser from "@apidevtools/json-schema-ref-parser";
import { jsonSchemaToZod } from "json-schema-to-zod";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCHEMAS_DIR = resolve(__dirname, "..");
const OUTPUT_FILE = resolve(__dirname, "..", "..", "packages", "sdk-ts", "src", "types.ts");

const SCHEMAS: Array<[file: string, name: string]> = [
  ["skill.schema.json", "skillSchema"],
  ["rule.schema.json", "ruleSchema"],
  ["ticket.schema.json", "ticketSchema"],
  ["simulation_report.schema.json", "simulationReportSchema"],
];

async function main(): Promise<void> {
  let output = `import { z } from "zod";\n\n`;
  for (const [file, name] of SCHEMAS) {
    const dereferenced = await $RefParser.dereference(resolve(SCHEMAS_DIR, file));
    const generated = jsonSchemaToZod(dereferenced, { module: "esm", name });
    const exportLine = generated.split("\n").find((line) => line.startsWith("export const"));
    if (!exportLine) {
      throw new Error(`failed to generate zod schema for ${file}`);
    }
    output += `${exportLine}\n\n`;
  }
  writeFileSync(OUTPUT_FILE, output);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
