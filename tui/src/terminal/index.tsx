import { createCliRenderer, type InputRenderable } from "@opentui/core"
import { render, useKeyboard } from "@opentui/solid"
import { createSignal, onMount } from "solid-js"
import { resolveThemeDocument } from "@opencode/theme/tui"
import { Research } from "@opencode/schema/research"
import { getOpenCode2Theme } from "@opencode/theme/tui/nia"
import { ResearchView } from "./view"

export interface Host {
  catalog(): Promise<readonly Research.Dataset[]>
  create(fileID: Research.FileID): Promise<{ id: string; research?: Research.Binding }>
  get(id: string): Promise<{ id: string; research?: Research.Binding }>
  prompt(id: string, text: string, progress: (event: { type: string; tool?: string }) => void): Promise<Research.Answer>
  interrupt(id: string): Promise<unknown>
  source(id: string, evidenceID: string): Promise<Research.Evidence>
  remove(id: string): Promise<void>
}

export async function runResearchTerminal(options: { host: Host; fileID?: Research.FileID; sessionID?: string }) {
  const renderer = await createCliRenderer({ exitOnCtrlC: false, useKittyKeyboard: {} })
  const theme = resolveThemeDocument(getOpenCode2Theme(), process.env.COLORFGBG?.endsWith(";15") ? "light" : "dark")
  await new Promise<void>((resolve, reject) => {
    renderer.once("destroy", resolve)
    function App() {
      const [catalog, setCatalog] = createSignal<readonly Research.Dataset[]>([])
      const [session, setSession] = createSignal<{ id: string; research?: Research.Binding }>()
      const [answer, setAnswer] = createSignal<Research.Answer>()
      const [transcript, setTranscript] = createSignal("")
      const [sources, setSources] = createSignal<string>()
      const [status, setStatus] = createSignal("Connecting to the qualified read-only database…")
      const [error, setError] = createSignal<string>()
      const [busy, setBusy] = createSignal(false)
      let input: InputRenderable | undefined
      const exit = () => resolve()
      useKeyboard((key) => {
        if (!key.ctrl || key.name !== "c") return
        const selected = session()
        if (busy() && selected) {
          void options.host.interrupt(selected.id)
          return
        }
        exit()
      })
      onMount(async () => {
        const load = async () => {
          setCatalog(await options.host.catalog())
          if (options.sessionID) setSession(await options.host.get(options.sessionID))
          if (options.fileID) setSession(await options.host.create(options.fileID))
          setStatus(session() ? "Ready" : "Enter one of the authorized list numbers below")
        }
        await load().catch(() =>
          setError("Could not open the research Session. Check authorization and connection configuration."),
        )
      })
      const submit = async () => {
        if (!input || busy()) return
        const text = input.value.trim()
        input.value = ""
        if (!text) return
        setError(undefined)
        if (text === "/quit") {
          exit()
          return
        }
        if (text === "/forget") {
          const selected = session()
          if (!selected) return
          setBusy(true)
          await options.host
            .remove(selected.id)
            .then(() => {
              setSession(undefined)
              setAnswer(undefined)
              setTranscript("")
              setSources(undefined)
              setStatus("Local Session and evidence deleted. Select one list for a new Session.")
            })
            .catch(() => setError("Could not delete this Session"))
            .finally(() => setBusy(false))
          return
        }
        if (text === "/sources") {
          if (sources()) {
            setSources(undefined)
            return
          }
          const selected = session()
          const current = answer()
          if (!selected || !current) return
          setBusy(true)
          await Promise.all(current.evidence.map((item) => options.host.source(selected.id, item.id)))
            .then((items) => setSources(JSON.stringify(items, null, 2)))
            .catch(() => {
              setAnswer(undefined)
              setSources(undefined)
              setError("Source evidence is stale or no longer authorized. Ask again for current evidence.")
            })
            .finally(() => setBusy(false))
          return
        }
        if (text === "/new") {
          setSession(undefined)
          setAnswer(undefined)
          setTranscript("")
          setSources(undefined)
          setStatus("Select one list for a NEW Session; the old Session retains its list")
          return
        }
        setBusy(true)
        const work = async () => {
          const selected = session()
          if (!selected) {
            const dataset = catalog().find((item) => item.fileID === Number(text))
            if (!dataset) throw new Error("Select an authorized list number")
            setSession(await options.host.create(dataset.fileID))
            setStatus("Ready · list selected permanently")
            return
          }
          setSources(undefined)
          const reply = await options.host.prompt(selected.id, text, (event) =>
            setStatus(event.tool ? `Research: ${event.tool}` : event.type),
          )
          setAnswer(reply)
          setTranscript((current) => `${current}${current ? "\n\n" : ""}You: ${text}\n\n${reply.text}`)
          setStatus("Ready")
        }
        await work()
          .catch(() => {
            setError("The reply failed or was interrupted.")
            setStatus("Ready")
          })
          .finally(() => setBusy(false))
      }
      return (
        <box flexDirection="column" width="100%" height="100%">
          <ResearchView
            theme={theme}
            label={
              session()?.research
                ? Research.labels[session()?.research?.fileID ?? 49]
                : catalog()
                    .map((item) => `${item.fileID}: ${item.label}`)
                    .join(" · ")
            }
            sessionID={session()?.id}
            answer={transcript() || answer()?.text}
            sources={sources()}
            status={status()}
            error={error()}
          />
          <input
            ref={(element) => {
              input = element
            }}
            focused={!busy()}
            placeholder={session() ? "Message…" : "List number…"}
            onSubmit={() => {
              void submit()
            }}
            textColor={theme.text.formfield.base}
            focusedTextColor={theme.text.formfield.base}
            backgroundColor={theme.background.formfield.base}
          />
        </box>
      )
    }
    void render(App, renderer).catch((error: unknown) => {
      reject(error)
    })
  }).finally(() => {
    // Unwind input submission before releasing its native input/render buffers.
    if (renderer.isDestroyed) return
    return renderer.idle().finally(() => renderer.destroy())
  })
}
