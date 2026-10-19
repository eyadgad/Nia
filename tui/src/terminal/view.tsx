import { For, Show } from "solid-js"
import type { ResolvedTheme } from "@opencode/theme/tui"

export function ResearchView(props: {
  theme: ResolvedTheme
  label: string
  sessionID?: string
  answer?: string
  status: string
  error?: string
  sources?: string
}) {
  return (
    <box flexDirection="column" flexGrow={1} backgroundColor={props.theme.background.base} padding={1}>
      <text flexShrink={0} fg={props.theme.text.base}>{`Nia · ${props.label}`}</text>
      <text flexShrink={0} fg={props.theme.text.muted}>
        {props.sessionID
          ? `${props.sessionID} · list fixed for this Session · latest published version`
          : "Choose exactly one list to create a Session"}
      </text>
      <scrollbox flexGrow={1} marginTop={1}>
        <For
          each={(
            props.sources ??
            props.answer ??
            "Say hello, ask what this list can answer, or ask a question about the records."
          ).split("\n")}
        >
          {(line) => (
            <text fg={props.theme.text.base} wrapMode="word">
              {line || " "}
            </text>
          )}
        </For>
      </scrollbox>
      <Show when={props.error}>
        <text flexShrink={0} fg={props.theme.text.feedback.error.base}>
          {props.error}
        </text>
      </Show>
      <text flexShrink={0} fg={props.theme.text.feedback.info.base}>
        {props.status}
      </text>
      <text flexShrink={0} fg={props.theme.text.muted}>
        /sources · /new · /forget · /quit · Ctrl-C interrupt/exit · reset filters by asking a new cohort question
      </text>
    </box>
  )
}
