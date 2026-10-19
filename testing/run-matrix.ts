// Ask every template question once per model slot. Resume skips filled cells.
// Concurrency is 4 against the local database. Four remote list reads hit the 10s cutoff.
//
//   bun testing/run-matrix.ts

import { Database } from "bun:sqlite"
import { existsSync } from "node:fs"
import { mkdir, rename } from "node:fs/promises"
import path from "node:path"
import { SQL } from "bun"

const root = path.resolve(import.meta.dirname, "..")
const outDir = path.join(root, "testing", "out")
const resultsPath = path.join(outDir, "results.json")
const logPath = path.join(outDir, "results.tsv")
const templatePath = path.join(root, "testing", "results_template.json")
const concurrency = 4
const questionTimeoutMs = 12 * 60 * 1000
const levels = new Set(["none", "minimal", "low", "medium", "high", "xhigh"])

type Cell = Record<string, unknown>
type Question = {
  id: string
  file_id: number
  question: string
  expected_answer: string
  model_results: Record<string, Cell>
}
type Sheet = { questions: Question[] }

const envText = await Bun.file(path.join(root, ".env")).text()
const databaseURL = envText.match(/^NIA_DATABASE_URL=(.*)$/m)?.[1]?.trim()
if (!databaseURL) throw new Error("NIA_DATABASE_URL is missing")

const parseSlot = (slot: string) => {
  const split = slot.lastIndexOf("_")
  const suffix = split < 0 ? "" : slot.slice(split + 1)
  if (!levels.has(suffix)) return { model: slot }
  return { model: slot.slice(0, split), effort: suffix }
}

const pending = (cell: Cell) => cell.answer === "" && cell.error == null

await mkdir(outDir, { recursive: true })
if (!(await Bun.file(resultsPath).exists())) await Bun.write(resultsPath, await Bun.file(templatePath).text())
const sheet = (await Bun.file(resultsPath).json()) as Sheet
if (!(await Bun.file(logPath).exists())) {
  await Bun.write(logPath, "started_at\tquestion\tslot\texit_code\telapsed_ms\tstored\n")
}

let writing = Promise.resolve()
const save = (question: Question, slot: string, cell: Cell, line: string) => {
  const run = writing.then(async () => {
    question.model_results[slot] = cell
    const temporary = `${resultsPath}.tmp`
    await Bun.write(temporary, `${JSON.stringify(sheet, null, 4)}\n`)
    await rename(temporary, resultsPath)
    await Bun.write(logPath, (await Bun.file(logPath).text()) + line)
  })
  writing = run.then(
    () => undefined,
    () => undefined,
  )
  return run
}

const jobs: { question: Question; slot: string }[] = []
for (const question of sheet.questions) {
  for (const slot of Object.keys(question.model_results)) {
    if (pending(question.model_results[slot])) jobs.push({ question, slot })
  }
}

const database = new SQL({ url: databaseURL, max: 1, connectionTimeout: 20, ssl: "disable" })
const health = async (fileID: number) => {
  const started = performance.now()
  const rows = await database`SELECT research_api.catalog('principal-researcher', ${fileID}, true) AS value`
  const value = rows[0].value as { label: string }
  return { ms: Math.round(performance.now() - started), label: value.label }
}

const usage = (stateDir: string) => {
  const file = path.join(stateDir, "sessions.sqlite")
  if (!existsSync(file)) return { input: "", output: "", reasoning: "", reported: "" }
  const db = new Database(file, { readonly: true })
  try {
    const session = db
      .query("SELECT tokens_input, tokens_output, tokens_reasoning FROM session_v2 ORDER BY time_updated DESC LIMIT 1")
      .get() as { tokens_input: number; tokens_output: number; tokens_reasoning: number } | null
    const messages = db.query("SELECT data FROM session_message WHERE type = 'assistant'").all() as { data: string }[]
    const reported = [
      ...new Set(
        messages.map((message) => {
          const model = (JSON.parse(message.data) as { model?: { id?: string } }).model
          return model?.id ?? ""
        }).filter(Boolean),
      ),
    ].join(", ")
    return {
      input: session ? String(session.tokens_input) : "",
      output: session ? String(session.tokens_output) : "",
      reasoning: session ? String(session.tokens_reasoning) : "",
      reported,
    }
  } catch {
    return { input: "", output: "", reasoning: "", reported: "" }
  } finally {
    db.close()
  }
}

const evidenceOf = (value: unknown) => {
  if (!value || typeof value !== "object" || !("evidence" in value)) return []
  const evidence = (value as { evidence?: unknown }).evidence
  if (!Array.isArray(evidence)) return []
  return evidence.map((item) => {
    const record = item as { id?: string; total?: number; query?: { operation?: string } }
    return { id: record.id ?? "", operation: record.query?.operation ?? "", total: record.total ?? null }
  })
}

const ask = async (question: Question, slot: string) => {
  const selected = parseSlot(slot)
  const startedAt = new Date()
  const stateDir = path.join(outDir, "state", `${question.id}-${slot}-${startedAt.getTime()}`)
  await mkdir(stateDir, { recursive: true })
  let healthMs = ""
  let label = question.file_id === 49 ? "Student master list" : "Confirmed deaths"
  try {
    const check = await health(question.file_id)
    healthMs = String(check.ms)
    label = check.label
  } catch {
    healthMs = ""
  }
  const child = Bun.spawn(["bun", "start", "--list", String(question.file_id), "--json", question.question], {
    cwd: root,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      ...process.env,
      NIA_STATE: stateDir,
      NIA_MODEL: `xai/${selected.model}`,
      NIA_REASONING_EFFORT: selected.effort ?? "",
    },
  })
  const timer = setTimeout(() => child.kill(), questionTimeoutMs)
  const started = performance.now()
  const [stdout, stderr, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ])
  clearTimeout(timer)
  const elapsed = Math.round(performance.now() - started)
  const finishedAt = new Date().toISOString()
  const tokens = usage(stateDir)
  let text = ""
  let version: number | null = null
  let answeredAt = ""
  let evidence: { id: string; operation: string; total: number | null }[] = []
  const jsonStart = stdout.indexOf("{")
  const jsonEnd = stdout.lastIndexOf("}")
  if (code === 0 && jsonStart >= 0 && jsonEnd > jsonStart) {
    const parsed = JSON.parse(stdout.slice(jsonStart, jsonEnd + 1)) as {
      text?: string
      version?: number
      at?: string
    }
    text = parsed.text ?? ""
    version = parsed.version ?? null
    answeredAt = parsed.at ?? ""
    evidence = evidenceOf(parsed)
  }
  const stored = text.length > 0
  const cell: Cell = {
    ...question.model_results[slot],
    answer: text,
    input_tokens: tokens.input,
    output_tokens: tokens.output,
    reasoning_tokens: tokens.reasoning,
    model_requested: selected.effort ? `xai/${selected.model} effort=${selected.effort}` : `xai/${selected.model}`,
    models_reported: tokens.reported,
    pre_execution_health_ms: healthMs,
    response_labels_match_catalog: text.includes(label) ? "true" : "false",
    elapsed_ms: elapsed,
    started_at: startedAt.toISOString(),
    finished_at: finishedAt,
    exit_code: code,
    list_version: version,
    answered_at: answeredAt,
    evidence,
    error: stored ? "" : (stderr || stdout).replace(/\s+/g, " ").trim().slice(0, 500) || "No reply was produced",
  }
  const line = `${startedAt.toISOString()}\t${question.id}\t${slot}\t${code}\t${elapsed}\t${stored ? "answer" : "error"}\n`
  await save(question, slot, cell, line)
  console.log(`${question.id}\t${slot}\t${stored ? "answer" : "error"}\t${elapsed}ms`)
}

console.log(`remaining ${jobs.length} concurrency ${concurrency}`)
let cursor = 0
const worker = async () => {
  while (cursor < jobs.length) {
    const job = jobs[cursor]
    cursor += 1
    await ask(job.question, job.slot)
  }
}
await Promise.all(Array.from({ length: concurrency }, () => worker()))
await database.close()
console.log("matrix finished")
