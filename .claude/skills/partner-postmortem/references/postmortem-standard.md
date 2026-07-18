# FAST TRACK PARTNER POSTMORTEM STANDARD
**Version 2.0 — July 2026 | Owner: Head of SRE | Classification: Internal (template), Confidential (completed reports)**

This document defines how Fast Track writes client-facing post-incident reports. It covers structure, tone, required facts, and quality gates. It is written to be executable by a human author or an AI agent: every section states what must be present, what good looks like, and what disqualifies a draft.

**v2.0 supersedes v1.1 entirely.** The reference format is the INC-10938 executive rewrite (CEO/CTO version). Changes from v1.1: formal third-person Provider/Client voice replaces the "you/we" personal voice; the "What This Means for You" and "Response Metrics" sections are removed; the document skeleton, timeline format, and closing disclaimer now follow the INC-10938 executive version exactly.

---

## PART 1 — PRINCIPLES

A world-class postmortem does six things. If a draft fails any of these, it is not done.

1. **It answers the client's five questions in the opening narrative.** What happened, what was affected, how badly, what caused it, what stops it happening again. A commercial director should be able to read only the opening narrative and brief their CEO accurately.
2. **It names the trigger precisely.** "A deployment to the Singularity Resources API corrupted the service's dashboard resources" — never "a fault occurred in a component." If the true cause is known, state it plainly; vagueness reads as evasion and destroys the credibility of everything around it. Owning the specific failure reads as *more* trustworthy, not less.
3. **It distinguishes deliberate actions from failures.** "The backoffice was taken offline as a precautionary measure while the investigation was ongoing" is materially different from "the backoffice went down" — and it is evidence of good judgment. Never let a controlled, protective decision read as an uncontrolled outage.
4. **It quantifies everything and tracks severity honestly.** Exact impact windows per affected service (they usually differ), durations, counts. Severity transitions are recorded: "P1 (Critical) until backoffice restoration (11:50 UTC); P2 thereafter." This bounds the critical window truthfully in both directions.
5. **It proves data safety rather than asserting it.** "No data loss" alone is insufficient for any incident involving corruption or a shared component. Explain *what the affected component holds and does not hold*, so the client can verify the reasoning: "The Singularity Resources API holds no client data — only the markup and code used by the dashboard container. No client data was altered or exposed."
6. **It is honest about detection.** If the client reported the issue before internal monitoring caught it, say so, and cross-reference the corrective action that fixes it. Hiding a bad detection story is worse than the story.

**The report is a product.** It is often the only artifact the client's leadership ever sees from the incident. It carries Fast Track's operational reputation.

---

## PART 2 — TONE AND LANGUAGE RULES

**Voice: formal, contractual, third person.** The report refers to **"the Provider"** (Fast Track) and **"the Client"** throughout. No "you", no "we", no direct address, no marketing-style sections. The document should read like a formal engineering record exchanged between two companies — precise, calm, and self-assured.

| Rule | Do | Don't |
|---|---|---|
| Name the trigger | "A deployment to the Singularity Resources API corrupted the service's dashboard resources." | "A fault in a central component required urgent remediation." |
| Deliberate vs failure | "The backoffice was taken offline as a precautionary measure while the investigation was ongoing." | "Remediation work took the dependent services offline." |
| Active voice, cause first | "The import process coerced 'true'/'false' strings to 0." | "Incorrect values were observed in the database." |
| Plain language | "The email provider blocked all sending for 10 hours." | "Email egress experienced a sustained throughput constraint." |
| Flat, technical, no heroics | "The fix was tested and deployed at 14:06." | "Our engineers worked tirelessly around the clock." |
| Describe the fix, never its magnitude | "Restoring Data Studio required a recovery job to restore the corrupted dashboard resources." | "Data Studio required a more substantial fix." |
| No minimising adverbs | "167,108 players received an incorrect bonus." | "A subset of players may have briefly received…" |
| Name systems, not people | "An operator command removed more capacity than intended; the tool did not enforce a floor." | "An engineer made a typo." |
| State uncertainty plainly | "The Provider was unable to reproduce the issue on Service X but rolled the change back as a precaution." | Silence about anything unconfirmed. |
| Explain longer restorations | "During the recovery the API was also moved to per-brand hosting; this is why Data Studio's restoration extended into 27 June." | An unexplained 28-hour gap. |

**Dates and times:**
- All times **UTC**. One timezone only.
- Prose and headers: "26 June 2026" (no ordinal suffixes — never "26th June").
- Timeline table: ISO format — `2026-06-26 09:00`.
- Impact windows written as "10:00 UTC, 26 June 2026 → 11:50 UTC, 26 June 2026 (1h 50m)" — always with the computed duration.
- Impact windows run from **first client impact to verified restoration** per service — never "declared to closed". Each affected service gets its own window; they usually differ (the trigger time and the protective-offline time are different events).
- Time-of-day words must agree with the stated UTC time: never "restored on the afternoon of 26 June at 11:50 UTC" — 11:50 UTC is not afternoon. When a timestamp is given, drop the time-of-day word.

**Placeholders:** A published report contains **no `XX:XX` or unresolved placeholders**. If a timestamp cannot be established, either cut the row or mark it explicitly `[HH:MM]` pending confirmation — permissible only for [COMMS] rows awaiting comms-log verification, and flagged in the internal author's note. Template fill-ins (`[Client / brand name]`, `[Report date]`) must be resolved before the report leaves the Provider.

**Language:** UK English exclusively — organisation, behaviour, analyse, prioritise, centre, licence (noun) / license (verb). Correct product names — Fast Track CRM, Fast Track AI, Rewards, Greco, Singularity Model, RTD.

**Forbidden:** "unforeseen circumstances"; "perfect storm"; "human error" as a root cause (the tooling or process that allowed it is the cause); "we apologise for any inconvenience"; "isolated incident"; self-praise of any kind ("industry-leading", "world-class"); humour or wit anywhere; minimisers attached to quantified impact; blame-shifting to third-party suppliers (name them factually; the Client's contract is with the Provider); vague fault language ("an issue occurred", "a fault was experienced") when the specific trigger is known; dramatic characterisation of the Provider's own work — magnitude adjectives ("substantial", "significant", "major", "complex", "extensive", "challenging") applied to a fix, effort, or investigation. State what was done; the reader infers the scale from the facts.

**Severity:** always stated with its transition history when severity changed during the incident: *"P1 (Critical) until backoffice restoration (11:50 UTC, 26 June); P2 thereafter – Resolved; corrective actions completed."* The downgrade also appears as a timeline row.

**The human test:** read the opening narrative aloud. It should sound like a capable engineering organisation explaining, precisely and without defensiveness, what happened. Not marketing, not legal.

---

## PART 3 — DOCUMENT STRUCTURE

The skeleton below is the INC-10938 executive format. Sections in this order; Required = the report cannot be published without it.

### 3.1 Header Block (required)

Title: **Incident Report INC-XXXXX**. Then a metadata table:

| Field | Rule |
|---|---|
| Incident ref | Internal reference (e.g. INC-10938) |
| Client environment | Client / brand name |
| Date of incident | Date(s), e.g. "26 June 2026" |
| Report date | Publication date |
| Severity / Status | P-level **with transition history and resolution state**: "P1 (Critical) until backoffice restoration (11:50 UTC, 26 June); P2 thereafter – Resolved; corrective actions completed" |
| Classification | "Confidential – shared between the Provider and the Client" |

### 3.2 Opening Narrative (required, unheaded, directly after the header table)

Three paragraphs of plain prose — no heading, no bullets. This is the section a CEO reads.

1. **Trigger and immediate effect.** The specific change and mechanism ("On 26 June 2026 at 09:00 UTC a deployment to the Singularity Resources API corrupted the service's dashboard resources"), what the affected component is and — critically — what it does *not* hold ("it holds no client data"), which services became unavailable and why, and any deliberate protective decision, framed as such ("at 10:00 UTC the backoffice was taken offline as a precautionary measure while the investigation was ongoing").
2. **What kept working, and restoration.** What was unaffected and why ("The core CRM engine does not depend on this component and continued to run throughout — all lifecycles, activities and send-outs executed as scheduled, no campaign was halted and there was no data loss"), then each restoration with its timestamp, including an explanation of any extended restoration ("the API was also moved from a central, shared service to per-brand hosting; this removed the central dependency and is why Data Studio's restoration took longer").
3. **Closure.** One line: "No further impact was observed following restoration."

**Disqualifiers:** passive-voice trigger sentence; vague cause; a protective action framed as an outage; missing restoration times; any sentence a commercial director could not parse.

### 3.3 Incident Overview (required)

Dash-bulleted fact list — the scannable version of the narrative:

- **Primary impacted systems:** partner-recognisable service names.
- **Not affected:** what kept running; explicit "no data loss".
- **Origin:** one sentence naming the trigger and the dependency that propagated it.
- **Impact window** — one bullet **per affected service**, each with start → end (UTC, full dates) and computed duration. The windows differ when trigger time and protective-offline time differ; report both honestly.
- **Detection method:** how the Provider first learned of the impact. If detection came from client reports, state it and cross-reference the corrective action ("availability alerting on the backoffice was insufficient to detect the loss of service internally first (addressed under CA-02)").
- **Severity / Status:** with transition history, matching the header.

### 3.4 Root Cause Analysis (required)

Prose, then bullets. Structure:

**Prose (2–3 paragraphs):**
1. What the affected component is, what it holds, and — for any incident touching data — what it does **not** hold. This paragraph is the data-safety proof.
2. What the trigger did, mechanically, and how the fault propagated to each affected service; any point where the cause was not yet known and a precautionary decision was taken, stated as such; how the investigation identified the origin.
3. The restoration path, including why any service's restoration took longer (e.g. a structural fix performed during recovery), and what structural change resulted.

**Bullets (each one line, bolded label):**
- **Key enabler:** the architectural condition that let one fault affect multiple services (e.g. "a single shared central component created a common dependency").
- **Contributing factor(s):** conditions that enlarged impact or delayed detection — each must map to a corrective action.
- **Mitigation:** what fixed it and what structural change prevents recurrence, with inline CA references ("…now runs as a local, per-brand service, removing the single point of dependency (CA-01). Availability alerting has been added to the backoffice service (CA-02).").

Apply five-whys internally before writing; publish the synthesis, not the Q&A scaffolding. Real component names, real mechanisms — vagueness here destroys the credibility built everywhere else.

### 3.5 Impact Assessment (required)

Dash bullets, quantified from the Client's perspective:

- **Availability, per affected service:** window (start → end, UTC, full dates), duration, what the Client's teams could not do, and operational context ("including during Friday campaign preparation"). Protective offlines described as such.
- **Campaign execution / core operations:** what ran unaffected, stated positively and precisely ("all lifecycles, activities and email and action send-outs ran as planned; no campaign was halted").
- **Data integrity:** not just "no data loss" — the *reasoning*: what the affected component holds, why the damage was bounded, confirmation of full restoration, and the explicit closing sentence "No client data was altered or exposed."
- **Collateral impact:** anything beyond the listed services, or "none identified beyond the services listed above." Never bury collateral damage; clients always find it.

Every number exact or explicitly approximate ("~28h"). Every anomaly mentioned anywhere in the report is either explained or marked under investigation — unexplained loose threads are credibility leaks.

### 3.6 Timeline of Key Events (UTC) (required)

Italic lead line: *Rows marked [COMMS] are communications between the Provider and the Client.*

**Three-column table: Timestamp (UTC) | Action | Description.**

- Timestamps in ISO format (`2026-06-26 09:00`); `~` for approximations; day-level rows ("2026-06-26 evening") acceptable for multi-hour work blocks.
- **Action** is a 1–3 word category label: *Deployment fault, Impact reported, Incident declared, Precautionary measure, Origin identified, Scope confirmed, Mitigation, Severity downgraded, Stabilisation, Development, Deployment, [COMMS] Client informed.*
- **Description**: factual, ≤ 2 sentences, no editorialising.
- Required rows: trigger; first client impact / impact reported; incident declared; every deliberate protective action; origin identified; scope confirmed; each restoration; **each severity transition**; each [COMMS] exchange in both directions.
- No `XX:XX`. `[HH:MM]` only on [COMMS] rows pending comms-log confirmation.

**Disqualifiers:** mixed timezones; two-column format; gaps > 1 hour during active response with no row explaining what was happening; editorial rows ("team worked diligently").

### 3.7 Containment and Remediation Measures (required)

Dash bullets, chronological — what was done, when, and what it achieved:

- Protective actions taken before the cause was known, framed as deliberate ("Took the backoffice offline as a precautionary measure when it began behaving irregularly, before the cause had been identified.").
- Interim restorations with timestamps.
- The permanent fix, distinguished explicitly from the interim measure, with inline corrective-action references and status: "…removing the single point of dependency (**CA-01 – completed**)."
- Detection improvements: "(**CA-02 – completed**)."

Completed corrective actions are referenced inline this way. **If any corrective action is still open at publication**, add a compact table after the bullets — ID | Action | Owner (team) | Due date | Status — and commit in Next Steps to a written status update on a named date. An action without a date is a wish.

### 3.8 Next Steps (required)

Dash bullets, forward-looking:

- Continued monitoring of the Client environment following the fix.
- A **systemic review commitment** — extending the lesson beyond this incident ("Review of availability alerting coverage across other client-facing services to confirm equivalent detection is in place."). Every postmortem closes with at least one action that generalises the lesson.
- Status-update date for any open corrective actions.
- Contact route: "Questions are welcome through the Client's usual contact at the Provider, or the Provider's Head of SRE, who owns this report."

### 3.9 Confidentiality Footer (required)

Verbatim, italic, at the end of the document:

> *This document is confidential and shared solely between the Provider and the Client for the purpose of incident review and remediation. It must not be distributed, reproduced, or disclosed to any third party without prior written consent. Findings reflect the Provider's assessment as of the report date and may be updated if new information becomes available.*

### 3.10 Appendices (optional)

Raw delivery logs, affected activity IDs, query outputs, glossary. Anything that serves auditors but would clog the narrative.

---

## PART 4 — QUALITY GATE (AI-AGENT CHECKLIST)

A draft must pass all gates before publication. Each item is evaluable as pass/fail.

**Completeness — facts that must exist:**
- [ ] Header block complete: incident ref, client environment, date of incident, report date, severity/status with transition history, Confidential classification
- [ ] Trigger named as a specific change/deployment/command with its mechanism ("deployment corrupted dashboard resources"), not a vague fault
- [ ] Every deliberate protective action identified and framed as precautionary, with its own timestamp distinct from the trigger
- [ ] Impact window per affected service (first client impact → verified restoration, UTC, with duration) — windows differ when trigger and protective-offline differ
- [ ] Severity transitions recorded in header, overview, and as timeline rows
- [ ] Detection method stated honestly; client-reported detection cross-referenced to its corrective action
- [ ] Data-safety reasoning present: what the affected component holds and does not hold; "No client data was altered or exposed" (or the factual equivalent)
- [ ] Extended restorations explained (why one service took longer)
- [ ] Interim measure vs permanent fix distinguished
- [ ] Every RCA contributing factor maps to a corrective action and vice versa
- [ ] Completed CAs referenced inline with status; open CAs in a table with owner and due date, plus a status-update date in Next Steps
- [ ] Next Steps includes a systemic review commitment and the contact route
- [ ] Confidentiality footer present verbatim
- [ ] No dangling facts — every anomaly explained or explicitly under investigation
- [ ] **No `XX:XX` or unresolved placeholders anywhere**; `[HH:MM]` only on [COMMS] rows pending confirmation

**Tone and voice — automatic flags:**
- [ ] Third person throughout: "the Provider" / "the Client" — no "you", "we", "our", "your" (flag every instance)
- [ ] No marketing-style sections or direct-address headings ("What you experienced", "What this means for you")
- [ ] No passive voice in the opening narrative's first sentence
- [ ] No forbidden phrases (Part 2 list); no self-praise; no humour
- [ ] No dramatic characterisation of fixes or effort — flag magnitude adjectives ("substantial", "significant", "major", "complex", "extensive") attached to the Provider's own work; the fix is described, not sized
- [ ] No named or identifiable individuals
- [ ] No minimisers attached to quantified impact
- [ ] Protective decisions never read as outages, and outages never read as maintenance

**Format and consistency — cross-checks:**
- [ ] Section order matches Part 3 exactly; no extra sections
- [ ] Timeline is three-column (Timestamp | Action | Description), ISO timestamps, monotonic
- [ ] Single timezone (UTC); prose dates "26 June 2026" (no ordinals); timeline `2026-06-26 09:00`
- [ ] Time-of-day words ("morning", "afternoon", "evening") agree with the accompanying UTC timestamp — flag any mismatch
- [ ] Every timestamp/duration in the narrative matches the timeline and the impact windows
- [ ] Severity in header matches overview and timeline transition rows
- [ ] Affected services in the overview all appear in the narrative and timeline
- [ ] UK English throughout (flag: organization, behavior, analyze, apologize, center)
- [ ] Product names correct (Fast Track CRM, Fast Track AI, Rewards, Greco, Singularity Model, RTD)
- [ ] No broken formatting: no stray bold markers, no empty headings, no missing spaces after full stops

**Escalation rule for the agent:** if any *Completeness* item cannot be filled from available inputs (incident channel, logs, timeline), output a **MISSING INFORMATION** list addressed to the incident commander rather than guessing. Fabricated facts in a postmortem are a severity-one documentation failure.

---

## PART 5 — WORKED EXAMPLE: BEFORE / AFTER (INC-10938)

The gold-standard reference is the INC-10938 executive rewrite. These are the actual deltas between the first draft and the published version — each is a rule in this standard.

**Vague fault → named trigger:**
> *Before:* "The root cause was a fault in the central Singularity Resources component."
> *After:* "On 26 June at 09:00 UTC a deployment to the Singularity Resources API corrupted the dashboard resources it holds."

**Outage framing → precautionary framing (and a factual correction):**
> *Before:* "Urgent remediation work on that component took the dependent services offline while it was carried out."
> *After:* "At that point the cause of the irregular behaviour was not yet known, and at 10:00 UTC the backoffice was taken offline as a precautionary measure while the investigation was ongoing."

**Flat severity → transition history:**
> *Before:* "Severity: P1"
> *After:* "P1 (Critical) until backoffice restoration (11:50 UTC, 26 June); P2 thereafter – Resolved; corrective actions completed" — with a "Severity downgraded" timeline row.

**Assertion → data-safety proof:**
> *Before:* "…and there was no data loss."
> *After:* "The Singularity Resources API holds no client data – only the markup and code used by the dashboard container to display dashboards – so the corruption was limited to those dashboard resources, which were fully restored by the recovery job. No client data was altered or exposed."

**Dramatic characterisation → the fix itself:**
> *Before:* "Data Studio required a more substantial fix: its access to the central Singularity Resources component was re-architected…"
> *After:* "Restoring Data Studio required a recovery job to restore the corrupted dashboard resources." — the work is named, not sized; the reader infers the scale from the facts.

**Placeholders → resolved timestamps:**
> *Before:* "26th June XX:XX — Partner impact reported"
> *After:* "2026-06-26 09:35 | Impact reported | First client reports received that the backoffice and Data Studio were unavailable."

**Single impact window → per-service windows:**
> *Before:* both services from 10:00 UTC.
> *After:* Data Studio 09:00 UTC (the deployment) → 13:00 UTC 27 June; backoffice 10:00 UTC (the precautionary offline) → 11:50 UTC.

**Point fixes only → systemic Next Steps:**
> *Before:* two corrective actions, both scoped to this incident.
> *After:* adds "Review of availability alerting coverage across other client-facing services to confirm equivalent detection is in place."

---

## PART 6 — PROCESS NOTES

- **Gold-standard reference:** the INC-10938 executive rewrite. Match its structure, voice, and depth exactly. (The former reference, INC-85241 v2.0, predates the v2.0 format.)
- **Internal vs client version:** the internal postmortem may contain client-identifying details, personnel context, and commercial discussion. The client version is derived from it, never the reverse. Same facts, same numbers — redaction only, no re-narration.
- **Publication SLA:** preliminary summary within 48 hours of resolution; full report within 5 business days; revised versions are versioned and change-logged ("Findings reflect the Provider's assessment as of the report date").
- **Review chain:** author (IC or SOC Team Lead) → Head of SRE → CTO for P1s → publish. The AI agent runs the Part 4 gate before each human review.
- **Action follow-through:** corrective actions are tracked in the incident tooling; any status-update date committed in Next Steps is a calendar commitment, not decoration. A postmortem whose actions silently expire is worse than no postmortem.
- **Document output — match the INC-10938 executive Doc exactly** (Google Doc `1Tnd6YTRiLZM-XNDuaZvFimzouuqqC4FRRU_1CGMkjxY`); this is a formal engineering record, not a branded campaign:
  - Typeface **Inter Tight** throughout (Arial fallback in docx). All text **black on white — no accent colour anywhere** (no purple headers, no coloured severity tokens).
  - Title `Incident Report INC-XXXXX`: 17pt bold. Section headers: 12pt bold, **Title Case** ("Incident Overview", "Root Cause Analysis", "Impact Assessment", "Timeline of Key Events (UTC)", "Containment and Remediation Measures", "Next Steps") — never ALL-CAPS, no underline/rule.
  - Body prose 10pt. Bulleted sections are **en-dash paragraphs** (`–` + hanging indent), not round bullets; lead-in labels bold at body size ("**Primary impacted systems:** …").
  - Tables (metadata block, timeline, open-CA table): 1pt `#bfbfbf` borders; label column / header row cells `#edf0f6` background with 10pt bold black text; metadata values 10pt; timeline and CA body cells 8pt. Metadata label column ≈137pt wide.
  - Timeline lead line (*Rows marked [COMMS]…*) and the confidentiality footer: italic 8pt.
  - **Yellow highlight `#ffff00` means exactly one thing:** content pending confirmation — the `[HH:MM]` [COMMS] rows (highlight all three cells' text). Nothing else is ever highlighted; a published final report contains no yellow.
  - Page footer with incident ID, version, classification, page number (native Docs footer — added manually when exporting via the Drive connector, which cannot write header/footer regions).
