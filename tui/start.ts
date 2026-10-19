import { mkdtemp, rm } from "node:fs/promises"
import os from "node:os"
import path from "node:path"

// Keep user-supplied query/provider paths relative to the download root.
process.chdir(path.resolve(import.meta.dirname, ".."))

// An explicit provider file keeps its existing settings. The simple setup stores only an env reference to the key.
const modelIndex = process.argv.indexOf("--model")
const model =
  process.argv.find((argument) => argument.startsWith("--model="))?.slice("--model=".length) ??
  (modelIndex < 0 ? undefined : process.argv[modelIndex + 1]) ??
  process.env.NIA_MODEL ??
  process.env.OPENCODE_RESEARCH_MODEL
const baseURL = process.env.NIA_BASE_URL
const reasoningEfforts = ["none", "minimal", "low", "medium", "high", "xhigh"]
const reasoningEffort = process.env.NIA_REASONING_EFFORT?.trim()
if (reasoningEffort && !reasoningEfforts.includes(reasoningEffort))
  throw new Error("NIA_REASONING_EFFORT must be one of: none, minimal, low, medium, high, xhigh")
const directory =
  model &&
  baseURL &&
  !process.env.NIA_PROVIDERS &&
  !process.env.OPENCODE_RESEARCH_PROVIDERS &&
  !process.argv.some((argument) => argument === "--help" || argument === "-h")
    ? await mkdtemp(path.join(os.tmpdir(), "nia-provider-"))
    : undefined

try {
  if (directory && model) {
    const separator = model.indexOf("/")
    if (separator < 1 || separator === model.length - 1) throw new Error("NIA_MODEL must be provider/model-id")
    process.env.NIA_PROVIDERS = path.join(directory, "provider.json")
    await Bun.write(
      process.env.NIA_PROVIDERS,
      JSON.stringify({
        [model.slice(0, separator)]: {
          package: "aisdk:@ai-sdk/openai-compatible",
          settings: { baseURL, apiKey: "{env:NIA_API_KEY}" },
          models: {
            [model.slice(separator + 1)]: {
              capabilities: { tools: true },
              ...(reasoningEffort ? { settings: { reasoningEffort } } : {}),
              limit: { context: 32000, output: 4096 },
            },
          },
        },
      }),
    )
  }
  await import("./src/cli")
} finally {
  if (directory) await rm(directory, { recursive: true, force: true })
}
