# NIA Standalone: complete system flowchart

This review describes the first-party runtime in `frontend/`, `backend/app/`,
`services/whisper/`, `voice_cli.py`, and `infra/`. Tests, benchmark drivers,
database-review notebooks, generated caches, and reference repositories are not
runtime blocks.

Planner routing: `PLANNER_MODE=ai` (default, Phase 2) is the active flow in
section 4. The 15-gate tree in section 4.1 is the `PLANNER_MODE=legacy`
emergency rollback path and is unchanged until Phase 3.

Legend:

- Solid arrow: active runtime call or data flow.
- Dashed arrow: configuration, fallback, optional provider, or operational path.
- PostgreSQL access from the assistant runtime is intended to pass through
  `assistant_api` views/functions or assistant-owned tables.

## 1. Whole-system context

```mermaid
flowchart LR
    U[Researcher]
    W[Existing NIA website]
    C[Terminal voice_cli.py]

    subgraph Browser[Next.js browser client]
        PAGE[HomePage<br/>auth, dataset picker, chat, history]
        APIJS[lib/api.ts<br/>cookie fetch + SSE parser]
        VOICEJS[lib/voice.ts<br/>LiveKit room + mic + data events]
        VBAR[VoiceBar<br/>waveform, mute, interrupt, end]
        PAGE --> APIJS
        PAGE --> VOICEJS
        VOICEJS --> VBAR
    end

    subgraph Core[FastAPI Assistant Core]
        MW[RateLimitMiddleware + CORS]
        AUTH[Auth API + AuthAdapter]
        HTTP[Assistant, token, speech, health APIs]
        TURN[AssistantTurnService]
        PLAN[Planning pipeline]
        EXEC[QueryExecutor + DagScheduler]
        MEM[Conversation memory]
        OBS[Tracing + audit + query-run persistence]
        MW --> AUTH
        MW --> HTTP
        HTTP --> TURN
        TURN --> PLAN
        PLAN --> EXEC
        TURN <--> MEM
        TURN --> OBS
        EXEC --> OBS
    end

    subgraph Voice[Realtime voice plane]
        LK[Self-hosted LiveKit]
        AG[LiveKit agent worker<br/>Silero VAD + ResearchVoiceAgent]
        STTA[WhisperCppSTTProvider]
        TTS[TTSProvider boundary]
        AG --> STTA
        AG --> TURN
        AG --> TTS
    end

    subgraph SpeechServices[Speech services]
        WH[Local Whisper service<br/>HTTP + WebSocket sessions]
        XAITTS[xAI speech WebSocket]
        KOKORO[Kokoro FastAPI]
    end

    subgraph Reasoning[Structured language model]
        XAI[xAI reasoning<br/>TurnPlan + optional synthesis]
    end

    subgraph Data[PostgreSQL]
        APIV[assistant_api<br/>authorized views/functions]
        OWN[assistant schema<br/>memory, traces, audit, jobs]
        RESEARCH[allowed research tables]
        BLOCKED[blocked website/auth/support tables]
        APIV --> RESEARCH
        APIV -. no grant .-> BLOCKED
    end

    JOB[Background worker<br/>retention / rebuild jobs]

    U --> PAGE
    W -->|signed website scope token| AUTH
    C -->|login, query, speech| MW
    APIJS -->|HTTPS + HttpOnly cookie + SSE| MW
    VOICEJS <-->|WebRTC audio + data| LK
    HTTP -->|mint scoped room token| LK
    LK <--> AG
    STTA <--> WH
    TTS -->|configured provider| XAITTS
    TTS -. configured provider .-> KOKORO
    PLAN -->|structured TurnPlan| XAI
    TURN -->|optional grounded synthesis| XAI
    EXEC --> APIV
    MEM --> OWN
    OBS --> OWN
    JOB --> OWN
```

## 2. Authentication and authorization flow

```mermaid
flowchart TD
    R[Incoming request] --> RL[Per-process route rate limit]
    RL --> A{Authorization header<br/>or session cookie?}
    A -->|none| E401[401 missing authorization]
    A -->|cookie on mutation| ORIGIN[Validate Origin / Fetch Metadata]
    A -->|Bearer| BUILD[build_auth_adapter]
    ORIGIN --> BUILD
    BUILD --> MODE{AUTH_ADAPTER}
    MODE -->|standalone| SJ[StandaloneJwtAuthAdapter]
    MODE -->|website| WA[WebsiteAuthAdapter]
    SJ -->|POST login| PASS[Check configured demo credentials]
    PASS --> SCOPE[Immutable AccessScope]
    WA -->|POST session| UP[Verify upstream issuer, audience,<br/>expiry and permission claims]
    UP --> SCOPE
    SJ -->|subsequent token| SCOPE
    WA -->|assistant cookie token| SCOPE
    SCOPE --> COOKIE[Issue/refresh HttpOnly SameSite cookie]
    SCOPE --> CORE[Assistant Core receives only<br/>principal + allowed file IDs + flags]
    CORE --> NARROW[AccessScope.narrow selected dataset]
    NARROW --> VALIDATE[Plan validator checks scope again]
    VALIDATE --> DB[assistant_api rechecks principal,<br/>requested IDs and private-file flag]
```

The two authentication modes replace only the identity source. Planning,
execution, memory, voice, STT, TTS, reasoning, and citations consume the same
`AccessScope` type.

## 3. Text query flow

```mermaid
flowchart TD
    Q[Researcher submits question] --> SQ[HomePage.sendQuestion]
    SQ --> STREAM[streamQuery POST /api/assistant/query<br/>Accept: text/event-stream]
    STREAM --> AUTHZ[get_access_scope]
    AUTHZ --> NOTTS[ensure_no_tts_in_text_mode]
    NOTTS --> START[SSE plan_started]
    START --> ANSWER[AssistantTurnService.answer]
    ANSWER --> LOAD[Parallel load:<br/>planning catalog + conversation]
    LOAD --> SELECT[Resolve/pin selected dataset]
    SELECT --> SELERR{Selection valid?}
    SELERR -->|no| SERR[dataset unavailable / mismatch / conflict]
    SELERR -->|yes| FAN{Question explicitly names<br/>multiple authorized lists?}
    FAN -->|yes| BRANCH[Run one isolated branch per list<br/>then merge labelled answers]
    FAN -->|no| NARROW[Narrow AccessScope to one dataset]
    NARROW --> ROUTE[plan_user_turn]
    ROUTE --> OUT{Route result}
    OUT -->|reference| REF[Answer prior row/result/ordinal]
    OUT -->|conversation or clarification| DIRECT[Program/compiler direct reply]
    OUT -->|access or field failure| FAIL[Fail-closed response]
    OUT -->|validated QueryPlan| RUN[_run_plan]
    RUN --> PV[SSE plan_validated]
    PV --> DAG[QueryExecutor.execute<br/>DagScheduler.run]
    DAG --> DB[DataGateway -> assistant_api]
    DB --> REDUCE[Reduce step outputs into facts,<br/>rows, evidence and run trace]
    REDUCE --> RC[SSE retrieval_completed + computed_fact]
    RC --> SYN{Grounded synthesis required<br/>and reasoner available?}
    SYN -->|no| FORMAT[Deterministic formatter]
    SYN -->|yes| LLM[Evidence packet -> reasoning provider<br/>validate answer citations]
    FORMAT --> RESULT[TurnResult]
    LLM --> RESULT
    REF --> RESULT
    DIRECT --> RESULT
    FAIL --> RESULT
    SERR --> RESULT
    BRANCH --> RESULT
    RESULT --> SAVE[Update memory + save conversation]
    RESULT --> QR[Persist query plan/run/step timings]
    RESULT --> AUDIT[Record audit event]
    SAVE --> SSE[SSE answer_delta, citation,<br/>memory_update, answer_completed]
    QR --> SSE
    AUDIT --> SSE
    SSE --> UI[Update chat, structured lists,<br/>citations and conversation sidebar]
    STREAM -. disconnect .-> CANCEL[CancellationToken cancels<br/>unused model/DAG work]
```

## 4. Ordered planning decision tree

```mermaid
flowchart TD
    IN[Final normalized user turn] --> EMPTY{Empty or incomplete<br/>voice utterance?}
    EMPTY -->|yes| CLARIFY[Direct clarification]
    EMPTY -->|no| FAST[trusted_fast_turn]
    FAST --> FOK{Trusted zero-model<br/>TurnPlan found?}
    FOK -->|yes| TV[validate_turn_plan]
    TV --> ROUTE[_route_validated_turn]
    FOK -->|no| ANALYTIC{Analytic question?}
    ANALYTIC -->|no, schema-priority| SP[parse_schema_query]
    SP --> COVER1[plan_covers_question]
    COVER1 -->|covered| EXP1[expand_plan_values]
    EXP1 --> QV1[validate_query_plan]
    ANALYTIC -->|otherwise| DP[parse_deterministic<br/>legacy mature fast paths]
    SP -->|no plan| DP
    DP --> COVER2[plan_covers_question]
    COVER2 -->|covered| EXP2[expand_plan_values]
    EXP2 --> QV2[validate_query_plan]
    COVER2 -->|not covered / needs planning| SP2[second schema parse<br/>unless active explicit follow-up]
    SP2 -->|covered| QV1
    SP2 -->|no plan| SC[SemanticCompiler.compile]
    ANALYTIC -->|yes| SC
    SC -->|provider unavailable / invalid output| NEED[Safe clarification / needs reasoning]
    SC -->|structured TurnPlan| OVR[apply_trusted_overrides]
    OVR --> TV2[validate_turn_plan]
    TV2 --> POLICY[decide_final_response]
    POLICY --> KIND{Action kind}
    KIND -->|reference| REF[Reference previous result]
    KIND -->|clarify| CLARIFY
    KIND -->|conversation| RESP[canned/compiler response]
    KIND -->|data action| BUILD[build_query_plan]
    BUILD --> EXP3[expand_plan_values]
    EXP3 --> QV3[validate_query_plan]
    QV1 --> PLAN[Validated QueryPlan]
    QV2 --> PLAN
    QV3 --> PLAN
    ROUTE --> PLAN
```

### 4.0 Active AI planner flow (`PLANNER_MODE=ai`)

```mermaid
flowchart TD
    IN[Final user text or STT transcript] --> NORM[Transport-only normalize]
    NORM --> EMPTY{Empty?}
    EMPTY -->|yes| STOP[Didn't catch that]
    EMPTY -->|no| SEL{Selected list or pin?}
    SEL -->|no| PICK[dataset_selection_required]
    SEL -->|conflict| CONF[dataset_scope_conflict]
    SEL -->|ok| PRI[Primary structured PlannedTurn]
    PRI -->|unavailable / invalid twice| FAIL[planner_unavailable or planner_invalid_output]
    PRI -->|ok| BIND[bind_scope selected file_id]
    BIND --> VAL[Strict TurnPlan + requirement parity]
    VAL --> BUILD[QueryPlan build + predicate contract]
    BUILD --> REV{Self-review}
    REV -->|complete or review slop| EXP[Value expansion + plan validate]
    REV -->|corrected| BIND
    REV -->|needs_clarification| ASK[Clarification]
    REV -->|provider down| FAIL
    EXP --> EXEC[QueryExecutor]
    EXEC --> ANS[Deterministic answer or synthesis]
```

Dataset scope is the UI selection or conversation pin only. The model never
emits file IDs. Other authorized list names may appear as `dataset_not_selected`.

### 4.1 Legacy 15-gate tree (`PLANNER_MODE=legacy` rollback)

The planner is called only for a final text message or final STT transcript. Partial
voice hypotheses are display-only and cannot start planning.

| Order | Gate | Rule and outcome |
|---:|---|---|
| 1 | Input normalization | Apply Unicode NFKC; normalize quotes/non-breaking spaces; resolve only one-token letter/year self-corrections; remove speech fillers and a small set of polite wrappers; collapse punctuation and whitespace. The normalizer never paraphrases. Remaining correction markers make the deterministic parser abstain. |
| 2 | Empty/incomplete guard | Empty input returns “didn’t catch that.” Voice text ending like an unfinished fragment returns a clarification before any model or database call. |
| 3 | Scope/context construction | Restrict the field catalog to `AccessScope`; attach active query, topic frames, last action keys, recent memory, user display name, and previous assistant text. |
| 4 | Trusted fast turn | Try only high-confidence program rules. Cause-of-death summaries deliberately bypass this gate so they retain evidence and synthesis. Query fast exits are limited to bounded random samples, a pure “list students” request, and an unambiguous named-person follow-up. |
| 5 | Analytic guard classification | Percentage, superlative/ranking, statistics, duplicate, distinct, “each/per,” and missing-bucket shapes skip legacy deterministic/schema shortcuts that could collapse them into a count or arbitrary row page. |
| 6 | Schema-priority parse | For a non-analytic schema-priority question, try the catalog-driven parser before the legacy grammar. Accept only an unambiguous operation, field, and value and only when `plan_covers_question` succeeds. |
| 7 | Legacy deterministic parse | For non-analytic turns, try the mature zero-model grammar and conversation-follow-up resolver. It requires complete semantic coverage (`min_coverage=1.0`) and otherwise abstains. |
| 8 | Second schema parse | If the legacy result is `needs_planning`, try the schema parser unless this is an active-query follow-up with explicit cues such as next, previous, same, also, add, those, or each one. |
| 9 | Semantic compiler | Send the scoped catalog and conversation state to the structured provider, requesting a typed `TurnPlan`. Malformed provider output is retried once. Provider failure returns a safe clarification; it never falls through to raw SQL or an unvalidated answer. |
| 10 | Trusted post-compiler overrides | Correct high-confidence conversational, paging, projection, sample, reference, and analytic shapes in the typed output. Dataset/filter choices remain subject to validation. |
| 11 | Turn validation | Enforce action, confidence, scope, field, operator, aggregate, evidence, follow-up, and injection rules. |
| 12 | Response route | Reference actions read prior results; clarification/conversation actions return program-owned text; data actions continue to deterministic query-plan construction. |
| 13 | Query-plan build | Convert effective query actions into one or more independent DAG branches. Model output is not executable and never supplies SQL. |
| 14 | Value expansion | Clean filter articles/punctuation, correct a value assigned to the wrong semantic field when ownership is unique, expand field-registry synonym families, and exclude literal unknown labels for `IS_KNOWN`. |
| 15 | Query-plan validation | Enforce injection, budgets, scope, DAG, operation contracts, feature gates, catalog capabilities, sorting, and evidence sensitivity. Only success reaches `QueryExecutor`. |

### 4.2 Trusted fast-path and post-compiler override flow

```mermaid
flowchart TD
    T[Typed or seed TurnPlan + original text] --> CS{Cause-of-death summary?}
    CS -->|yes in fast path| SEM[Require semantic compiler]
    CS -->|yes after compiler| SYN[Keep scoped query;<br/>force evidence + explanation + synthesis]
    CS -->|no| CONV{Exact conversational rule?}
    CONV -->|greeting / thanks / farewell| RESP[Program-owned respond action]
    CONV -->|assistant or user identity / introduction| RESP
    CONV -->|speak / sing / available-data request| RESP
    CONV -->|confusion or non-research correction| RESP
    CONV -->|no| CAT{Requested catalog field absent?}
    CAT -->|yes| FIELDMSG[Explain available scoped fields]
    CAT -->|no| SAMPLE{Random/sample student request?}
    SAMPLE -->|yes| SAMP[Bounded list sample;<br/>default 5, maximum 50;<br/>project name and named dates]
    SAMPLE -->|no| PROJ{All information or<br/>add fields beside rows?}
    PROJ -->|yes| PROJECT[Goal list + catalog fields + table;<br/>preserve active query when modifying]
    PROJ -->|no| WIN{First/last N result window?}
    WIN -->|yes| WINDOW[Anchor start/end; size <= 5000;<br/>page <= 50; reset cursor]
    WIN -->|no| YES{Bare affirmation?}
    YES -->|after voice offer| VOICE[Voice capability response]
    YES -->|after page offer + active query| NEXTP[Modify previous: next page]
    YES -->|otherwise| ACK[Acknowledgement]
    YES -->|not affirmation| REF{Model emitted row reference<br/>without explicit ordinal?}
    REF -->|yes| CORR[Replace with correction response]
    REF -->|no| LIST{List/follow-up rule?}
    LIST -->|pure list students| STUDENTS[Exhaustive sorted numbered list;<br/>page 25]
    LIST -->|next / previous| PAGE[Modify previous page]
    LIST -->|challenge previous answer| VERIFY[VerifyPreviousAction]
    LIST -->|list them / alphabetically / one by one| ENUM[Modify previous to exhaustive<br/>sorted numbered list]
    LIST -->|named person follow-up| PERSON[Name filter + all other public fields]
    LIST -->|none| RESET[Reset accidental offset/page unless<br/>the user explicitly asked next/previous]
    RESET --> GENERAL{Only general conversation?}
    GENERAL -->|yes| GSAFE[Compiler response; confidence >= .9;<br/>disable evidence/inference]
    GENERAL -->|no| DUMP{Non-research text produced<br/>bare unfiltered research query?}
    DUMP -->|yes| GSAFE
    DUMP -->|no| ANALYTIC[Apply analytic guards]
```

Trusted-rule details:

- A bare “yes/okay” becomes a voice action only after a voice offer, becomes next
  page only after a page offer with active state, and otherwise stays an
  acknowledgement.
- “What?” or confusion is not treated as a row reference. A row reference requires
  an explicit ordinal/index such as first, second, fifth, last, or an index 0–49.
- A new non-page request resets an accidental previous offset. Sampling clears
  offset, result window, and sorting.
- “All information” expands only to public fields on the already scoped dataset;
  it cannot pull fields from another list.
- Trusted replacements set confidence to at least 0.95 and deterministic response
  mode, but are still passed through `validate_turn_plan` and `validate_query_plan`.

### 4.3 Analytic correction rules

```mermaid
flowchart TD
    A[Compiled QueryAction] --> PCT{Percentage wording?}
    PCT -->|yes and goal list/count| GP[Force percentage]
    PCT -->|no but goal percentage| BACK[Return to rank if grouped,<br/>otherwise count]
    PCT -->|otherwise| DUP{Duplicate wording + group?}
    DUP -->|yes| GD[Force duplicates]
    DUP -->|no| SUP{Superlative/rank wording + group?}
    SUP -->|yes| GR[Force rank + requested top N]
    SUP -->|no| STAT{Stats wording + measurable field?}
    STAT -->|yes and goal list| GS[Force stats + stats aggregate]
    STAT -->|no| COUNT{How-many wording and no<br/>explicit list/fields?}
    COUNT -->|yes| GC[Force count]
    COUNT -->|no| GROUP{Count has group_by, or<br/>each/per/missing bucket?}
    GROUP -->|yes| BR[Force grouped rank;<br/>infer year/decade part;<br/>include missing bucket]
    GROUP -->|no| NAME[Resolve first/last-name field<br/>or token part]
    GP --> NAME
    BACK --> NAME
    GD --> NAME
    GR --> NAME
    GS --> NAME
    GC --> NAME
    BR --> NAME
    NAME --> SYNON[Expand registry synonym families]
    SYNON --> ALT[Merge positive alternatives on one field<br/>into CONTAINS_ANY]
    ALT --> POL[Correct IS_KNOWN to IS_UNKNOWN<br/>when negation precedes field]
    POL --> BUCKET[Remove same-field filter from<br/>a bucket breakdown]
    BUCKET --> DOSSIER{Person-summary wording?}
    DOSSIER -->|yes| DOS[Goal dossier; name search;<br/>clear narrowing filters]
    DOSSIER -->|no| INTERVAL{Elapsed-time wording?}
    INTERVAL -->|yes| DATES[Infer ordered life-event date pair;<br/>shortest=asc, longest=desc]
    INTERVAL -->|no| SANITIZE[Fill required aggregate/interval fields;<br/>drop unresolvable optional fields;<br/>stand down impossible goal safely]
    DATES --> SANITIZE
    DOS --> SANITIZE
    SANITIZE --> SAFE[Corrected QueryAction]
```

Analytic guards are application-owned corrections; they do not trust the model’s
chosen calculation shape. Their main invariants are:

- A calculation is never replaced by an arbitrary page of records.
- Multiple positive terms for one field are alternatives (`CONTAINS_ANY`), not an
  impossible AND of several `CONTAINS` filters.
- Historical spelling families come from field-registry `value_synonyms`, including
  correct negative-family operators.
- “No/missing/without field” is `IS_UNKNOWN`; “known/recorded field” is
  `IS_KNOWN`, with literal “Unknown” spellings excluded later.
- A grouped breakdown includes missing values only when asked and removes a filter
  on the same field so all requested buckets survive.
- Life-event intervals are ordered birth → admission → discharge → death → burial →
  registration regardless of the order in which events appear in the sentence.

### 4.4 Complete semantic compiler rule contract

The structured compiler is instructed with the following complete rule groups.
Application validation and trusted overrides remain authoritative if model output
conflicts with them.

| Prompt rules | Complete requirements |
|---|---|
| 1–5: safety and grounding | Never generate SQL; never invent datasets/fields; use only the authorized catalog; database facts require query actions; research facts cannot appear in respond actions. |
| 6–14: response and context | General conversation may respond; exact calculations are deterministic; interpretation/synthesis/judgment/narrative evidence uses LLM synthesis; preserve self-corrections; resolve confident follow-ups from active query; clarify only genuine ambiguity; preserve independent requests as independent actions; do not reveal inaccessible datasets; do not guess field meanings. |
| 15–16c: conversational intents | Identity, audio, greetings, thanks, farewells, capability, available-data, acknowledgements, user identity/introduction, corrections, and general conversation use their typed intents. “I am X” is user introduction; “who am I” is user identity; “who are you” is assistant identity. Non-research/general-knowledge work is general conversation with no query. References require explicit row/action ordinals and cannot invent a prior record. |
| 17–19: action structure | Independent requests remain separate query actions; unrelated filters are never ANDed together. Compare needs at least two branches; aggregate needs an aggregate spec; list plus `group_by` means presentation grouping. Clarify only when different interpretations would produce different queries, not merely because a question is hard. |
| 20–25: list/follow-up behavior | “List all/them/one by one” is exhaustive list, normally numbered. Pages default to 25 and max at 50; “all” is paginated. Next/show more modifies the previous list. “List them” after a count changes the goal to list. Challenges create `verify_previous`. Organized/alphabetical/one-by-one changes presentation/sort without losing dataset/filters. |
| 26–30: windows, projection, sampling | First/last N is a start/end result window with cursor 0 and page `min(N,50)`, never a remembered absolute offset. Adding fields beside prior rows modifies `requested_fields` while preserving filters/sort/window. New multi-field lists use table presentation. Random/sample is bounded sampling, not paging. Requiring admitted and discharged dates produces two `IS_KNOWN` filters and projects both fields. |
| 31–32: count/percentage | “How many/total” → count. “Percentage/proportion/share” → percentage, with subset filters in numerator and population filters in `denominator_filters`; empty denominator means the whole scoped dataset. |
| 33–34: rank/distinct | Most/fewest/top/rank/common/frequent → rank with the ranked field in `group_by` and requested `top_n`. Values listed/recorded/different/unique → distinct with that field in `group_by`. |
| 35–39: analytic goals | Youngest/oldest/average/median/how old → stats over a numeric/date field. Repeated/shared values → duplicates with group and optional companion field. Duration wording → interval with two date fields and asc/desc direction for shortest/longest. Most/least complete record → completeness. “Everything about person” → dossier + name search + LLM synthesis. |
| 40: time buckets | Per-year/per-decade grouping uses the corresponding value part on a date. A superlative inside each outer bucket uses outer group first and `per_group_top_n=1`. |
| 41–46: filters | Independent conditions are AND unless true either/or. Synonym families use `CONTAINS_ANY`; negatives use `NOT_CONTAINS_ANY`. “Other than” is a negative comparison, not missingness. Missing/without → `IS_UNKNOWN`; known/recorded → `IS_KNOWN`; known fields with literal Unknown also exclude that label. Preserve every stated condition. First/last/full names map to their catalog fields or name token parts. |
| 47–49: answer shape | Calculations must use their computation goal. “Who/which, all” uses exhaustive list with named fields. Counts, rankings, statistics, percentages, distinct values, duplicates, and intervals are deterministic; dossiers and genuinely interpretive questions use synthesis. |

The compiler request contains only: current utterance and mode; recent conversation;
active query; topic frames; last action keys; display name; scoped datasets and
field metadata; allowed operators; field types/capabilities; and registry synonym
families. It receives no SQL schema or direct database connection.

### 4.5 Deterministic and schema-parser acceptance rules

| Parser | Accepts | Mandatory abstention rules |
|---|---|---|
| Legacy deterministic parser | Explicit count/list; authorized dataset resolution; high-confidence name-prefix, community, year/date-event, deceased-state, distinct-field, bounded-list, and mature conversation-follow-up shapes. | Abstain for unresolved corrections, pronoun/referential follow-ups needing semantics, synthesis/explanation, typed aggregates, comparison/ratio/percentage/rank, negation/complex clauses, multiple actions, missing context, unsupported constraints, or any semantic content not fully consumed. |
| Schema-driven parser | A single selected dataset with an unambiguous catalog operation and field: count, distinct, distribution/mode, min/max, list, field presence/missingness, starts/contains, numeric/date values/ranges, named person, bounded sort/window. | Abstain for schema-description questions, random/sample, summary/why/explain, quote/provenance, each/per, organize, compare/versus/exclude, huge first/last windows, compound count-and-list, absent/ambiguous field, unresolved required predicate, or no explicit supported goal. |
| Coverage checker | Every content word must be query language, catalog vocabulary, or represented in the plan; every specifically named catalog field must be referenced by a field, predicate, sort, interval, or companion slot. | Any leftover value/field (for example a disease term not represented in predicates) rejects the fast plan and sends the turn to semantic compilation. |

### 4.6 Turn validation flow and rules

```mermaid
flowchart TD
    TP[TurnPlan] --> ORPHAN{Follow-up without<br/>active query?}
    ORPHAN -->|modify_previous| PROMOTE[Promote usable changes to new QueryAction]
    ORPHAN -->|only verify/reference remains| OCLARIFY[Clarify which records]
    ORPHAN -->|no| ACTIONS{Actions <= 8?}
    PROMOTE --> ACTIONS
    ACTIONS -->|no| REJECT[Reject with typed error code]
    ACTIONS -->|yes| CONF{Confidence < .75 and no<br/>executable/trusted conversation?}
    CONF -->|yes| CLOW[Clarification TurnPlan]
    CONF -->|no| UNRES{Unresolved items and no<br/>clarify/executable action?}
    UNRES -->|yes| CSPEC[Specificity clarification]
    UNRES -->|no| MIX{General conversation mixed<br/>with research actions?}
    MIX -->|yes| DROP[Drop general-conversation noise]
    MIX -->|no| EACH[Validate each action]
    DROP --> EACH
    EACH --> DATASET[Dataset named and authorized;<br/>scope catalog contains it]
    DATASET --> FILTERS[Every filter/denominator operator<br/>allowed on every selected dataset]
    FILTERS --> FIELDS[group/sort/companion/interval fields<br/>exist on every selected dataset]
    FIELDS --> CONTRACT[rank/duplicates require group;<br/>interval requires two dates;<br/>stats requires measure;<br/>compare >= 2 branches]
    CONTRACT --> AGG[Aggregate function has field and<br/>compatible numeric/ordered/text type]
    AGG --> FOLLOW[Modify/verify/reference requires active query;<br/>reference requires selector or index]
    FOLLOW --> RESPOND[Respond intent allow-listed;<br/>general response has no research claim]
    RESPOND --> EVID{needs_evidence?}
    EVID -->|yes| SENS[At least one selected field permits evidence]
    EVID -->|no| INJECT[Scan structural identifiers]
    SENS --> INJECT
    INJECT -->|SQL verb or blocked table token| REJECT
    INJECT -->|clean| VALID[Validated TurnPlan]
```

Turn validation scans structural identifiers, not user free text. A user may search
for words that resemble SQL; only action types, semantic field identifiers, group/
sort/aggregate fields, compare filters, and intent identifiers are protected from
SQL/table-name injection.

### 4.7 QueryPlan compilation rules and goal-to-DAG map

```mermaid
flowchart TD
    V[Validated data actions] --> EFFECT[Resolve QueryAction or replay/edit<br/>active query/topic frame]
    EFFECT --> MULTI{One action or several?}
    MULTI -->|one| ONE[One branch, action a0]
    MULTI -->|several| MANY[Independent prefixed branches a0..aN;<br/>union only the plan scope, not filters]
    ONE --> SRC[USE_CURRENT_VERSION from current_records]
    MANY --> SRC
    SRC --> FILT{Filters?}
    FILT -->|yes| F[FILTER with AND/OR predicate tree]
    FILT -->|no| SEARCH{search_text or search goal?}
    F --> SEARCH
    SEARCH -->|yes| RET[FTS + FUZZY in parallel<br/>→ UNION → DEDUPLICATE]
    SEARCH -->|no| GOAL{Goal compiler}
    RET --> GOAL
    GOAL --> TERMINAL[Goal-specific terminal steps]
    TERMINAL --> E{Evidence or synthesis requested?}
    E -->|yes and fields permit| EV[GET_EVIDENCE, max 8]
    E -->|no| PLAN[QueryPlan]
    EV --> PLAN
    PLAN --> CLEAN[expand_plan_values]
    CLEAN --> QVALID[validate_query_plan]
```

| Effective goal | Compiled DAG behavior |
|---|---|
| `count` | Optional filter/retrieval, optional per-dataset grouping for an unfiltered multi-file count, then `COUNT`; optional evidence. |
| `list` | Optional filter/retrieval, deterministic `SORT`, total `COUNT`, `SAMPLE` or bounded `LIMIT`, then catalog-approved `PROJECT`; optional evidence. |
| `search` | FTS + fuzzy branches → union → deduplicate → bounded projection and evidence. |
| `distinct` | `GROUP_BY` over one/two canonical fields with value-part, missing, having, top-N, and per-group controls. |
| `rank` | `RANK` over one/two group fields with optional top-N/per-group top-N and missing bucket. |
| `stats` | `STATS` over a resolved measure; optional parallel grouped `RANK`. |
| `aggregate` | Optional grouping followed by `COUNT`, `COUNT_DISTINCT`, `SUM`, `AVG`, `MIN`, or `MAX`. Median/mode/stats compile to the single `STATS` pass. |
| `percentage` | Independent numerator and denominator sources/counts, then `PERCENTAGE`; denominator filters define the population. |
| `compare` | At least two independent filter/search/count branches, then `COMPARE`. |
| `duplicates` | `DUPLICATES` on the group field with minimum count (default 2), optional companion, value part, and top N. |
| `interval` | `INTERVAL_STATS` using ordered start/end fields, bounds, direction, and a display-row limit. |
| `completeness` | `COMPLETENESS`, direction asc/desc, capped at 50 rows. |
| `quote` | `GET_QUOTE`, at most 8 rows, using quoteable evidence fields. |
| `provenance` | `GET_PROVENANCE`, default 20 and capped at 50. |
| `dossier` | Name retrieval → project every public field common to scope → evidence packet → synthesis goal. |
| `verify_previous` | Replay prior datasets/filters/search/fields as an exhaustive first page, clear prior result window, sort deterministically, and mark verification for the answer preface. |
| `modify_previous` | Preserve active query; upsert changed filters by field; apply page/window cursor, goal, limit, fields, sample, sort, presentation, or frame restoration without widening datasets. |

Bounded-output rules:

- Default list page: 25; maximum normal page/sample: 50.
- Explicit exhaustive enumeration ceiling: 200, still paginated in normal UI flow.
- Result-window size: 1–5000; page inside the window remains at most 50.
- Evidence/quote rows: at most 8.
- `group_by`: at most two fields; `per_group_top_n`: at most 50; general `top_n`:
  at most 500.

### 4.8 Final QueryPlan validation flow and rules

```mermaid
flowchart TD
    QP[Constructed QueryPlan] --> STRUCT[Structural injection scan:<br/>step IDs, ops, fields, predicates]
    STRUCT -->|blocked table or SQL verb| R[Reject]
    STRUCT -->|clean| BUDGET[Budgets: steps <= 24; files <= 8;<br/>inputs/step <= 8; search branches <= 8;<br/>query text <= 500]
    BUDGET -->|exceeded| R
    BUDGET -->|ok| SCOPE[authorized_only=true;<br/>non-empty scope; plan/step IDs subset<br/>of AccessScope]
    SCOPE -->|history without permission| R
    SCOPE -->|ok| DAG[Dependencies refer only to current_records<br/>or earlier unique step IDs]
    DAG -->|missing/duplicate dependency| R
    DAG -->|ok| FEATURE[History and attachment ops enabled?]
    FEATURE -->|disabled op| R
    FEATURE -->|ok| CONTRACT[Operation input/field/limit/window contracts]
    CONTRACT -->|invalid| R
    CONTRACT -->|ok| CATALOG[All predicate/step/sort/interval/companion<br/>fields resolve on every step dataset]
    CATALOG -->|unknown field or disallowed operator| R
    CATALOG -->|ok| CAP[Sort capability; evidence sensitivity;<br/>numeric/ordered aggregate capability]
    CAP -->|invalid| R
    CAP -->|ok| EXEC[Approved for QueryExecutor]
```

Operation contracts enforced at this layer include:

- Single-input operations must have exactly one dependency; union/intersection/
  difference/compare/ratio/percentage require at least two.
- `FILTER` needs predicates; `COUNT_DISTINCT`, `STATS`, and `DUPLICATES` need
  exactly one field; numeric aggregates need one numeric/ordered field.
- `SORT` needs a sortable field; `LIMIT`, `TOP_N`, and `SAMPLE` need a limit.
- Result-window anchor and size must appear together and only on `LIMIT`/`PROJECT`.
- `RANK` needs one or two group fields; intervals need both start and end fields.
- History is off by default and also requires `AccessScope.history_allowed`;
  attachment content is off by default.

### 4.9 Final response-policy rules

```mermaid
flowchart LR
    T[Validated TurnPlan] --> C{Only clarify or<br/>conversation actions?}
    C -->|yes| CR[compiler_response<br/>program/canned text]
    C -->|no| V{Verify previous?}
    V -->|yes| D[deterministic]
    V -->|no| I{needs_inference or needs_explanation<br/>or explicit llm_synthesis?}
    I -->|yes| L[Grounded LLM synthesis after execution]
    I -->|no| D
    T -->|only reference| R[Reference resolver;<br/>no new query plan]
```

Even when synthesis is selected, the deterministic plan executes first and builds a
bounded evidence packet. Synthesis output is accepted only after citation validation;
visible/stored answers cannot cite a source outside that packet.

Security invariants in the planning path:

- Model output is a typed `TurnPlan`; application code builds the `QueryPlan`.
- Both turn and query plans reject structural injection and unauthorized datasets.
- Fields, operators, aggregate capability, budgets, DAG dependencies, history use,
  and attachment use are validated against the scoped field catalog.
- The model never emits SQL and the runtime database role cannot read the blocked
  website tables.

## 5. Query execution, operations, and retrieval

```mermaid
flowchart TD
    P[Validated QueryPlan] --> SCHED[Convert PlanSteps to ScheduledSteps]
    SCHED --> READY[DagScheduler ready set]
    READY --> LIMITS[Global + DB + retrieval + LLM<br/>resource semaphores]
    LIMITS --> SF[Singleflight by idempotency key]
    SF --> TIMEOUT[Per-step timeout + cancellation]
    TIMEOUT --> OP{Plan operation}

    OP -->|scope/control| CTRL[USE_DATASET, USE_CURRENT_VERSION,<br/>FILTER, SORT, LIMIT, TOP_N]
    OP -->|record output| ROWS[PROJECT, SAMPLE]
    OP -->|counts/groups| AGG[COUNT, COUNT_DISTINCT, GROUP_BY,<br/>SUM, AVG, MIN, MAX, STATS]
    OP -->|quality/interval| QUAL[DUPLICATES, COMPLETENESS,<br/>INTERVAL, INTERVAL_STATS]
    OP -->|derived| DER[PERCENTAGE, RATIO, COMPARE, RANK]
    OP -->|search| SEARCH[EXACT_LOOKUP, FULL_TEXT_SEARCH,<br/>FUZZY_SEARCH]
    OP -->|set merge| SETS[UNION, INTERSECT, DEDUPLICATE]
    OP -->|grounding| EVID[GET_EVIDENCE, GET_QUOTE,<br/>GET_PROVENANCE, GET_RAW_FIELDS]

    SEARCH --> SCORE[Exact / FTS / fuzzy scorer]
    SCORE --> EARLY{Unique exact hit?}
    EARLY -->|yes| CANCELS[Cancel sibling search branches]
    EARLY -->|no| SETS
    CTRL --> GW[DataGateway]
    ROWS --> GW
    AGG --> GW
    QUAL --> GW
    SEARCH --> GW
    EVID --> GW
    GW --> PG[AssistantDataGateway<br/>parameterized assistant_api calls]
    GW -. dev/tests .-> MEMGW[MemoryDataGateway]
    PG --> REDUCE[_reduce -> ExecutionResult]
    MEMGW --> REDUCE
    SETS --> REDUCE
    DER --> REDUCE
    EVID --> PACK[build_evidence_packet]
    PACK --> REDUCE
    REDUCE --> TRACE[RunTrace: latency, queueing,<br/>parallel peak, critical path]
```

Declared `PlanOp` values that are not accepted by the current deterministic
executor/validator are reserved or handled earlier in planning: history-version,
previous-result/topic-frame resolution, alias/reference/entity/pronoun/ordinal
resolution, semantic search/classification, active-query edits, difference/exclude,
normalization, conflict checks, and approved attachments.

`HybridRetriever` is implemented and tested as a standalone exact/FTS/fuzzy
fan-out with entity resolution, deduplication, ranking, and early cancellation.
The active `QueryExecutor` currently performs the three search branches directly;
it does not instantiate `HybridRetriever`.

## 6. PostgreSQL authorization and storage boundary

```mermaid
flowchart LR
    EX[QueryExecutor] --> DG[AssistantDataGateway]
    DG --> FNS[assistant_api functions]
    FNS --> AUTHF[_authorized_file_ids]
    AUTHF --> POLICY[dataset_policy + access_grants]
    FNS --> VIEWS[v_current_records / v_current_raw_records<br/>v_datasets / v_dataset_fields]
    VIEWS --> DATA[authorized public research data]

    MEM[PostgresMemoryStore] --> MT[conversations, messages,<br/>conversation_state, query_frames,<br/>result_sets]
    OBS[Query-run and audit writers] --> OT[query_plans, query_runs,<br/>query_step_runs, audit_events]
    JOB[Job worker] --> JT[background_jobs + retention targets]

    RUNTIME[assistant_runtime role] -->|EXECUTE| FNS
    RUNTIME -->|CRUD| MT
    RUNTIME -->|CRUD| OT
    RUNTIME -->|CRUD| JT
    RUNTIME -. no direct grant .-> DATA
    RUNTIME -. revoked .-> SENSITIVE[users, roles, otps, logs,<br/>support and website operational tables]
    SELFTEST[privilege_selftest at production startup] --> RUNTIME
```

Data-gateway functions cover catalog loading, scoped counts, per-file counts,
grouping (one or two dimensions), statistics, duplicates, completeness, interval
rows/statistics, sorted/paginated/windowed lists, random samples, retrieval
candidates, evidence/raw-field reads, source-ID reads, and query-run persistence.

## 7. Realtime voice flow and barge-in

```mermaid
flowchart TD
    CONNECT[User clicks Connect voice] --> TOKEN[POST /api/livekit/token]
    TOKEN --> CHECK[Validate AccessScope, selected dataset,<br/>conversation pin and room namespace]
    CHECK --> MINT[Mint 15-minute token with signed<br/>scope metadata + agent dispatch]
    MINT --> ROOM[Browser joins LiveKit room<br/>and publishes microphone]
    ROOM --> AGENT[Agent worker accepts participant]
    AGENT --> META[scope_from_metadata + conversation ID<br/>+ selected file ID]
    META --> SESSION[AgentSession: Silero VAD,<br/>no preemptive generation, no LiveKit LLM]
    SESSION --> STT[LiveKit STT adapter]
    STT --> WSVC[Whisper service session]
    WSVC --> PARTIAL[Partial transcript]
    PARTIAL -->|UI only| DATA[LiveKit data message]
    WSVC --> FINAL[Final transcript after endpointing]
    FINAL --> HOOK[AssistantTurnHook.on_user_turn_completed]
    HOOK --> CORE[Same AssistantTurnService as text]
    CORE --> PHRASE[Spoken text / phrase callback]
    PHRASE --> CLEAN[Humanize + strip citations +<br/>optional restrained expression tags]
    CLEAN --> PROVIDER{TTS_PROVIDER}
    PROVIDER -->|xai| XAI[xAI WebSocket PCM]
    PROVIDER -->|kokoro| KOK[Kokoro HTTP PCM]
    XAI --> PLAY[LiveKit playback]
    KOK --> PLAY
    CORE --> EVENTS[assistant delta/reply/citation events]
    EVENTS --> DATA
    DATA --> UI[Browser transcript + answer + citations]

    BARGE[User speaks, presses Interrupt,<br/>or sends data command] --> INT[ResearchVoiceAgent.interrupt]
    INT --> FLUSH[Flush phrase queue + cancel TTS generation]
    INT --> CANCEL[Cancel unused reasoning/DAG work]
    FLUSH --> LISTEN[State returns to Listening]
    CANCEL --> LISTEN

    PREF[Male/female voice request] --> SWITCH[requested_voice_preference / set_voice]
    SWITCH --> RECONNECT[Provider switches voice and may greet]
```

Voice state machine: `Disconnected -> Connecting -> Ready -> Listening -> User
speaking -> Processing -> Assistant speaking`, with `Interrupted`, `Reconnecting`,
and `Error` transitions protecting invalid state changes.

## 8. Local Whisper service

```mermaid
flowchart TD
    IN[PCM16 mono audio] --> API{Interface}
    API -->|one shot| ONESHOT[POST /transcribe]
    API -->|session REST| OPEN[open -> audio chunks -> finalize/reset/close]
    API -->|streaming| WS[WebSocket control + binary PCM]
    OPEN --> SESSION[WhisperSession buffer]
    WS --> SESSION
    SESSION --> THRESH{Enough new audio for partial?}
    THRESH -->|yes| ENGINE[TranscriptionEngine.transcribe]
    THRESH -->|no| BUFFER[Keep buffering]
    ONESHOT --> ENGINE
    ENGINE --> KIND{Configured engine}
    KIND --> FW[FasterWhisperEngine]
    KIND --> CLI[whisper.cpp CliEngine]
    KIND -. tests .-> SCRIPT[ScriptedEngine]
    FW --> EVENT[TranscriptResult / TranscriptEvent]
    CLI --> EVENT
    SCRIPT --> EVENT
    EVENT -->|partial/final, text, confidence,<br/>duration, model| CLIENT[STT client / LiveKit adapter]
```

The service enforces a concurrent-session cap, expires idle sessions, buffers
audio per session, generates partials at an interval, and resets the session after
a final turn.

## 9. Memory, observability, and operations

```mermaid
flowchart TD
    TURN[Completed or interrupted turn] --> UPDATE[update_memory_from_turn]
    UPDATE --> TURNS[Append user + assistant turns]
    UPDATE --> STATE[Extract active QueryState]
    UPDATE --> FRAMES[Persist action/topic frames]
    UPDATE --> RESULTS[Persist bounded result-set rows + source IDs]
    UPDATE --> SUMMARY[Refresh title and rolling summary]
    SUMMARY --> STORE{MemoryStore}
    STORE -->|pool available| PGM[PostgresMemoryStore]
    STORE -. fallback/tests .-> IMM[InMemoryMemoryStore]

    TURN --> SPAN[turn / retrieval / llm / tts spans]
    TURN --> AUDIT[query_completed / denied / interrupted audit]
    TURN --> RUNS[plan + DAG run + step timings]
    SPAN --> OTEL[Optional OpenTelemetry + in-process trace list]
    AUDIT -->|pool available| PGA[assistant.audit_events]
    AUDIT -. fallback .-> MA[MemoryAuditor]
    RUNS --> PGR[assistant.query_plans / query_runs / query_step_runs]

    CRON[Operational invocation] --> QUEUE{Job queue}
    QUEUE -->|Postgres| PGQ[FOR UPDATE SKIP LOCKED lease]
    QUEUE -. fallback .-> MQ[MemoryJobQueue]
    PGQ --> WORK[worker.handle_job]
    MQ --> WORK
    WORK --> RET[RetentionService]
    WORK --> REBUILD[FTS / alias rebuild job kinds]
    RET --> SAFE[Delete assistant-owned expired data only]
```

## 10. Runtime endpoints and their functions

| Endpoint | Main function | Purpose |
|---|---|---|
| `GET /health` | `health` | Liveness and configured auth/reasoning status. |
| `GET /ready` | `readiness` | Concurrent checks of PostgreSQL, Whisper, LiveKit, and reasoning configuration. |
| `POST /api/auth/login` | `login` | Standalone credential check and session-cookie creation. |
| `POST /api/auth/session` | `exchange_website_session` | Exchange a website bearer token for an assistant cookie. |
| `GET /api/auth/session` | `browser_session` | Restore or clear the browser session. |
| `GET /api/auth/me` | `me` | Return and refresh the current scope. |
| `POST /api/auth/logout` | `logout` | Clear the assistant cookie. |
| `GET /api/assistant/datasets` | `list_datasets` | Return authorized datasets, fields, operations, and starter prompts. |
| `GET /api/assistant/conversations` | `list_conversations` | List principal-owned conversation summaries. |
| `GET /api/assistant/conversations/{id}` | `get_conversation` | Load one principal-owned conversation. |
| `POST /api/assistant/query` | `query` / `_stream_query` | Run the shared core synchronously or as SSE with cancellation. |
| `POST /api/livekit/token` | `create_token` | Validate dataset/conversation scope and mint a namespaced room token. |
| `POST /api/voice/speech` | `synthesize_speech` | Authenticated PCM speech stream for the terminal client. |

## 11. Block/function responsibility catalog

| Block | Primary classes and functions | Runtime responsibility |
|---|---|---|
| App bootstrap | `create_app`, `lifespan`, `init_pool`, `close_pool`, `validate_production_settings` | Configure middleware/routes, database lifecycle, and production fail-closed checks. |
| Web UI | `HomePage`, `restoreSession`, `sendQuestion`, `applyVoiceMessage`, `connectVoiceSession`, `ChatMessage`, `StructuredListResult` | Manage auth, dataset-scoped conversations, SSE rendering, voice state, rows, and citations. |
| Web API client | `authorizedFetch`, `login`, `fetchSession`, `fetchDatasets`, `fetchConversations`, `fetchConversation`, `streamQuery`, `parseSseBlock` | Cookie-authenticated HTTP and typed SSE consumption. |
| Browser voice | `connectVoice`, `requestedVoicePreference`, `waitForVoiceInput`, `startLevelMeter`, `VoiceBar` | LiveKit connection, microphone, audio attachment, data commands, waveform, and controls. |
| Auth | `AuthAdapter`, `build_auth_adapter`, `StandaloneJwtAuthAdapter`, `WebsiteAuthAdapter`, `get_access_scope` | Convert either identity source into immutable `AccessScope`; enforce cookie-origin checks. |
| Scope/token security | `AccessScope.allows_file`, `narrow`, `fingerprint`, `assigned_room_name`, `mint_livekit_token`, `scope_from_metadata` | Preserve least privilege through HTTP, planning, database calls, and voice rooms. |
| Assistant API | `_gateway`, `_turn_service`, `query`, `_stream_query`, `_as_sse`, `_serialize_turn` | Select production/fallback dependencies and expose progress/result events. |
| Turn orchestration | `AssistantTurnService.answer`, `_answer`, `_answer_fan_out`, `_run_plan`, `_direct_reply`, `_answer_reference`, `_answer_ordinal`, `_synthesize`, `_persist` | Dataset routing, planner invocation, execution, grounded answer production, and persistence. |
| Input/conversation planning | `normalize_user_turn`, `ConversationContext`, `trusted_fast_turn`, `parse_deterministic`, `parse_schema_query`, `SemanticCompiler.compile`, `apply_trusted_overrides` | Convert a final utterance and prior frames into trusted structured intent. |
| Plan construction/security | `validate_turn_plan`, `decide_final_response`, `build_query_plan`, `expand_plan_values`, `validate_query_plan`, `plan_covers_question` | Build only allow-listed, bounded, scoped DAGs from structured actions. |
| Plan models | `TurnPlan` action models, `QueryPlan`, `PlanScope`, `PlanStep`, `Predicate`, `PlanOp`, `FilterOperator` | Typed contracts between interpretation, validation, compilation, and execution. |
| Execution | `QueryExecutor.execute`, `_run_step`, `_reduce`, `DagScheduler.run`, `_run_one`, `_cancel_group`, `with_timeout`, `ResourceGate`, `Singleflight`, `CancellationToken` | Run independent plan steps concurrently with limits, timeouts, deduplication, and cancellation. |
| Filtering/projection/formatting | `predicate_matches`, `matches_predicate_tree`, `apply_predicates`, `public_projected_row`, `format_deterministic_answer`, `format_spoken_answer` | Apply typed predicates in fallback mode and expose only catalog-approved output. |
| Data gateway | `DataGateway`, `AssistantDataGateway`, `MemoryDataGateway` and their count/group/stats/list/sample/retrieve/evidence methods | Keep execution independent of PostgreSQL while enforcing scoped production calls. |
| Retrieval | `score_exact`, `score_fts`, `score_fuzzy`, `resolve_entity`, `dedupe_hits`, `rank_hits`, `HybridRetriever.retrieve`, `build_evidence_packet` | Score and merge search hits and construct bounded grounded evidence. |
| Reasoning | `get_reasoning_provider`, `XAIReasoningProvider.structured_output`, `SemanticCompiler.compile`, `_synthesize`, `validate_synthesis` | Structured intent and optional evidence-grounded prose; never database access. |
| Conversation memory | `default_memory_store`, `InMemoryMemoryStore`, `PostgresMemoryStore`, `update_memory_from_turn`, `extract_query_state`, `resolve_followup`, `resolve_listed_ordinal` | Principal isolation, durable shared text/voice history, frames, paging, and row references. |
| Realtime agent | `_agent_entry`, `ResearchVoiceAgent.handle_final_transcript`, `AssistantTurnHook.on_user_turn_completed`, `handle_voice_preference`, `interrupt`, `VoiceStateMachine.transition` | Bridge LiveKit final turns to the shared core and publish replies/citations/state. |
| STT adapter/service | `WhisperCppSTTProvider`, `create_livekit_stt`, `WhisperService`, `WhisperSession`, `build_engine`, engine `transcribe` methods | Convert PCM to partial/final transcripts locally. |
| TTS | `get_tts_provider`, `SpeechSession`, `PhraseBuffer`, `PhraseQueue`, `create_livekit_tts`, `XAITTSProvider`, `KokoroTTSProvider`, `humanize_for_speech`, expression helpers | Produce bounded, citation-free streamed speech with cancellation and voice switching. |
| Observability | `Tracer.span`, `default_auditor`, `PostgresAuditor.record`, `save_query_run` | Capture safe spans, authorization outcomes, and durable DAG performance. |
| Background jobs | `PostgresJobQueue`, `MemoryJobQueue`, `run_once`, `handle_job`, `RetentionService` | Lease, retry, complete, and safely purge/rebuild assistant-owned operational data. |
| Database lifecycle | `apply_migrations`, `assert_runtime_isolation` | Apply ordered SQL migrations and verify the runtime role cannot cross the privilege boundary. |
| Terminal client | `AssistantClient`, `WhisperClient`, `Microphone`, `BackendSpeaker`, `Speaker`, `run_text`, `run_voice`, `run_wav`, `_handle_utterance` | Alternate authenticated text/microphone/WAV client with local or backend speech. |

## 12. Review notes: active, fallback, and dormant paths

- Active production query path: API/voice -> `AssistantTurnService` -> planning router ->
  validated `QueryPlan` -> `QueryExecutor`/DAG -> `AssistantDataGateway` ->
  `assistant_api` -> formatting or grounded synthesis -> memory/audit.
- Development fallback: if the PostgreSQL pool is unavailable, API and voice may
  use `MemoryDataGateway`; memory and audit also have in-process fallbacks.
- `HybridRetriever` is tested but not wired into `QueryExecutor`; executor search
  steps implement equivalent direct exact/FTS/fuzzy branches.
- `vector_search.score_vector` is a deliberate empty stub; semantic/vector search
  is not an active runtime capability.
- `LLMTurnInterpreter`, `ConstrainedPlanner`, and
  `AssistantTurnService._reasoned_plan_and_answer` remain compatibility/legacy
  code. The current router uses `SemanticCompiler` for the model-backed planning
  path.
- The SQL schema includes forward-looking tables (feedback, voice sessions,
  attachments, citations) beyond the tables written by the current request path.
- The background worker handles retention and recognizes rebuild job kinds, but it
  is a one-shot operational command unless an external scheduler invokes it.

For the exhaustive source-symbol list (including private helpers), see
`docs/system-function-inventory.md`.
