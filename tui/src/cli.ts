#!/usr/bin/env bun

import { parseArgs } from "node:util"
import os from "node:os"
import path from "node:path"
import { Schema } from "effect"
import { Research } from "@opencode/schema/research"
import { ResearchHost } from "@nia/backend"
import { ensurePluginRuntime } from "@opencode/plugin/runtime"

const args = parseArgs({
  args: process.argv.slice(2),
  strict: true,
  allowPositionals: true,
  options: {
    list: { type: "string", multiple: true },
    session: { type: "string" },
    model: { type: "string" },
    state: { type: "string" },
    json: { type: "boolean" },
    query: { type: "string" },
    "query-file": { type: "string" },
    catalog: { type: "boolean" },
    help: { type: "boolean", short: "h" },
  },
})

if (args.values.help) {
  console.log(`Nia — one list per permanent Session

  bun run research --list 49 [question]
  bun run research --session ses_... [question]
  bun run research --list 91 --query '{"operation":"count"}' --json
  bun run research --catalog
  bun run research --list 91 --query-file count.json --json

Lists: 49 Master, 91 Confirmed deaths, 93 Additional Deaths, 94 Potential.
Select exactly one when creating a Session. Omit a question to open the terminal UI.
Required: NIA_DATABASE_URL and NIA_MODEL (or --model).
Optional server-owned settings: NIA_PRINCIPAL (default public),
NIA_PRIVATE=true, NIA_PROVIDERS=<JSON config file>,
NIA_SSL=verify-full (required remotely), NIA_STATE,
NIA_REASONING_EFFORT=none|minimal|low|medium|high|xhigh.
No ambient project configuration, shell, filesystem or web tools are enabled.`)
  process.exit(0)
}

async function main() {
  if ((args.values.list?.length ?? 0) > 1 || (args.values.list?.length && args.values.session))
    throw new Error("Choose exactly one list for a new Session, or resume a Session without a list selector")
  const url = process.env.NIA_DATABASE_URL ?? process.env.OPENCODE_RESEARCH_DATABASE_URL
  const model = args.values.model ?? process.env.NIA_MODEL ?? process.env.OPENCODE_RESEARCH_MODEL
  if (!url || (!model && !args.values.query && !args.values["query-file"] && !args.values.catalog))
    throw new Error("Configure NIA_DATABASE_URL and NIA_MODEL (see --help)")
  ensurePluginRuntime()
  const selectedModel = model ?? "openai/gpt-4.1"
  const provider = selectedModel.split("/")[0]
  const providerFile = process.env.NIA_PROVIDERS ?? process.env.OPENCODE_RESEARCH_PROVIDERS
  const providers = providerFile
    ? Schema.decodeUnknownSync(Schema.Record(Schema.String, Schema.Json))(await Bun.file(providerFile).json())
    : undefined
  const ssl = Schema.decodeUnknownSync(Schema.Literals(["disable", "verify-full"]))(
    process.env.NIA_SSL ?? process.env.OPENCODE_RESEARCH_SSL ?? "verify-full",
  )
  await using host = await ResearchHost.create({
    directory:
      args.values.state ??
      process.env.NIA_STATE ??
      process.env.OPENCODE_RESEARCH_STATE ??
      path.join(os.homedir(), ".opencode-research"),
    database: {
      url,
      principal: process.env.NIA_PRINCIPAL ?? process.env.OPENCODE_RESEARCH_PRINCIPAL ?? "public",
      private: (process.env.NIA_PRIVATE ?? process.env.OPENCODE_RESEARCH_PRIVATE) === "true",
      ssl,
    },
    model: selectedModel,
    allowedProviders: [provider],
    providers,
  })
  if (args.values.catalog) {
    console.log(JSON.stringify(await host.catalog(), null, 2))
    return
  }
  const fileID = args.values.list?.[0]
    ? Schema.decodeUnknownSync(Research.FileID)(Number(args.values.list[0]))
    : undefined
  const question = args.positionals.join(" ")
  if (!args.values.query && !args.values["query-file"] && !question && process.stdin.isTTY && !args.values.json) {
    const { runResearchTerminal } = await import("./terminal/index")
    await runResearchTerminal({ host, fileID, sessionID: args.values.session })
    return
  }
  if (!fileID && !args.values.session) throw new Error("New Sessions require exactly one --list selection")
  const session = args.values.session
    ? await host.get(args.values.session)
    : await host.create(Schema.decodeUnknownSync(Research.FileID)(fileID))
  const interrupt = () => {
    void host.interrupt(session.id)
  }
  process.on("SIGINT", interrupt)
  try {
    if (args.values.query || args.values["query-file"]) {
      if (args.values.query && args.values["query-file"]) throw new Error("Choose --query or --query-file")
      const query = args.values["query-file"]
        ? Schema.decodeUnknownSync(Research.Query, { onExcessProperty: "error" })(
            await Bun.file(args.values["query-file"]).json(),
          )
        : Schema.decodeUnknownSync(Schema.fromJsonString(Research.Query), { onExcessProperty: "error" })(
            args.values.query,
          )
      console.log(JSON.stringify({ sessionID: session.id, evidence: await host.query(session.id, query) }, null, 2))
      return
    }
    if (!question.trim()) throw new Error("A question or --query is required in headless mode")
    const answer = await host.prompt(session.id, question, (event) => {
      if (!args.values.json)
        process.stderr.write(
          event.type === "tool"
            ? `Research: ${event.tool}\n`
            : event.type === "working"
              ? `Session ${session.id} · ${session.research ? Research.labels[session.research.fileID] : "unbound"}\n`
              : "",
        )
    })
    console.log(args.values.json ? JSON.stringify(answer, null, 2) : answer.text)
  } finally {
    process.off("SIGINT", interrupt)
  }
}

await main().catch(() => {
  process.stderr.write(
    "Research request failed. Verify the selected list/Session, read-only gateway connection, provider configuration and query capabilities. No unverified answer was displayed.\n",
  )
  process.exitCode = 1
})
