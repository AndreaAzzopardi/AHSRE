# FAST TRACK PARTNER POSTMORTEM STANDARD
**Version 1.1 — June 2026 | Owner: Head of SRE | Classification: Internal (template), Confidential (completed reports)**
*Aligned with the Fast Track brand and tone of voice framework (UK English, six tone traits, partner-first positioning).*

This document defines how Fast Track writes partner-facing post-incident reports. It covers structure, tone, required facts, and quality gates. It is written to be executable by a human author or an AI agent: every section states what must be present, what good looks like, and what disqualifies a draft.

---

## PART 1 — PRINCIPLES

A world-class postmortem does five things. If a draft fails any of these, it is not done.

1. **It answers the partner's five questions in the first 200 words.** What happened, who was affected, how badly, what caused it, what stops it happening again. A commercial director should be able to read only the executive summary and brief their CEO accurately.
2. **It is cause-first and active-voice.** "A defect in our migration process caused X" — never "X was experienced by some players." We name the action, the system, and the failure. We never name the individual. (AWS convention: name the command, not the operator.)
3. **It quantifies everything.** Counts, rates, durations, percentages. "167,108 accounts" beats "a large number of accounts." Vague numbers signal that we don't understand our own incident.
4. **It is honest about detection and response, not just root cause.** The hardest section to write is "why we didn't catch this sooner." World-class postmortems (Anthropic's September 2025 report is the benchmark) explicitly admit evaluation gaps, slow detection, and confusing signals. Partners trust reports that include the uncomfortable parts.
5. **Every corrective action is verifiable.** Owner, due date, status, and a completion criterion. An action without a date is a wish. An action without a verification criterion can be marked "done" without changing anything.

**The communication is a product.** The report is often the only artifact the partner's leadership ever sees from this incident. It carries Fast Track's operational reputation.

---

## PART 2 — TONE AND LANGUAGE RULES

| Rule | Do | Don't |
|---|---|---|
| Active voice, cause first | "The import process coerced 'true'/'false' strings to 0." | "Incorrect values were observed in the database." |
| Plain language | "The email provider blocked all sending for 10 hours." | "Email egress experienced a sustained throughput constraint." |
| Flat, technical, no heroics | "The fix was tested and deployed at 14:06." | "Our engineers worked tirelessly around the clock." |
| No minimising adverbs | "167,108 players received an incorrect bonus." | "A subset of players may have briefly received…" |
| Name systems, not people | "An operator command removed more capacity than intended; the tool did not enforce a floor." | "An engineer made a typo." |
| State uncertainty plainly | "We were unable to reproduce the issue on Service X but rolled the change back as a precaution." | Silence about anything unconfirmed. |
| One timezone | All times in **UTC**, with CET in parentheses only in the header and executive summary. | Mixing CET and UTC mid-timeline. |
| Absolute dates | "17 March 2026, 03:01 UTC" | "yesterday morning," "last week" |
| No legal hedging in the narrative | Facts as established. | "allegedly," "it appears that," "we believe" (unless genuinely unconfirmed — then say *why* it's unconfirmed) |

**Forbidden phrases:** "unforeseen circumstances," "perfect storm," "human error" (as a root cause — it never is; the tooling or process that allowed it is), "we apologise for any inconvenience" (apologise specifically or not at all), "isolated incident" (you don't know that yet).

**Length targets:** Executive summary ≤ 250 words. Full report 1,200–2,500 words plus tables. If it's longer, the incident narrative has absorbed detail that belongs in tables or the timeline.

---

## PART 2B — SOUNDING LIKE FAST TRACK

A postmortem is not marketing, but it is brand. For many partner stakeholders it is the most consequential document Fast Track ever sends them — the brand promise ("we've got your back; we're your partner to the future") is tested precisely here, when something broke. The Fast Track tone framework applies, adapted for incident reporting:

| Trait | In a postmortem this means | Status |
|---|---|---|
| **Clear** | Ten words where others use fifty. No buzzwords, no filler, no consultancy prose. The partner's commercial team can read it unaided. | Required |
| **Informative** | The partner learns something real about their platform and our operations from every section. Technical depth is respect, not risk. | Required |
| **Bold** | Direct ownership. "Our import process coerced the values" — stated plainly, without softening, in the first paragraph. Bold is the confidence to own a failure without being asked. | Required |
| **Personal** | Written by people, to people. "You" and "we" throughout — never "the client" or "the vendor." Sign it from a named role. | Encouraged |
| **Optimistic** | Applies to the *future* sections only (corrective actions, closing). The forward path is framed through what becomes possible, not through fear of recurrence. It never applies to the facts: impact is stated at full weight, no silver-lining the numbers. | Encouraged (scoped) |
| **Witty** | Never. No humour anywhere in a postmortem. | Excluded |

**Language and naming rules:**

- **UK English exclusively** — organisation, behaviour, analyse, apologise, personalisation, licence (noun) / license (verb), centre, programme.
- **"Partner," never "customer" or "client."** Section 3.3 is "Partner Impact." This is the Fast Track relationship model, and it should be visible in our most difficult documents, not just our website.
- **Correct product names** — Fast Track CRM, Fast Track AI, Rewards, Greco, Singularity Model, RTD. Generic internal service names ("Lifecycle Engine," "Email Distributor") are fine for subsystems, but where a partner-facing product is involved, use its real name.
- **Own the outcome, including third parties.** Name suppliers factually ("Brevo blocked outbound sending in response to the volume") but never frame them as the cause — the partner's contract is with Fast Track, and the trigger was ours. Blame-shifting to a vendor fails the Bold trait and reads as exactly what it is.
- **No self-praise.** Never "our industry-leading response" or "our world-class SOC." The response metrics table makes the case or it doesn't. Show, never tell — the Leader archetype is expressed through the quality of the document, not claimed in it.
- **The content truth standard applies in full.** Every claim substantiated. If a number, timing, or cause cannot be proven, it is marked as under investigation — never asserted.
- **The human test.** Read the executive summary aloud. Does it sound like a capable person explaining what happened to someone they respect, or like a legal department? If the latter, rewrite.

**Document design (partner-facing PDF/docx output):**

- Typeface: **Inter Tight** (Arial fallback in docx)
- Headers: bold ALL-CAPS, left-aligned; black body text on white
- Official Fast Track colours only: FT Pink `#E96092`, FT Purple `#832081`, FT Blue `#63B6E6`, FT Yellow `#FFDB14`, FT Dark Orange `#E54F35`, FT Orange `#F4A300`
- Colour is functional, not decorative: FT Purple for section headers and table header rows; FT Dark Orange reserved for severity/impact callouts; FT Blue for partner-action items. Maximum two accent colours per report — a postmortem should look composed, not branded like a campaign.
- Footer on every page: incident ID, version, classification ("Confidential — prepared for [Partner]"), page number.

---

## PART 3 — DOCUMENT STRUCTURE

Sections in order. Required = report cannot be published without it.

### 3.1 Header Block (required)

A metadata table at the top:

| Field | Rule |
|---|---|
| Incident ID | Internal reference (e.g. INC-85241) |
| Severity | P-level **plus one-line definition** ("P1 — material impact to player-facing functionality for one or more partners") |
| Status | Resolved / Monitoring / Actions in progress |
| Affected services | Partner-recognisable names |
| Impact window | Start of customer impact → end of customer impact (UTC). Not "declared to closed" — partners care about when *they* were affected, not when our process started. |
| Detection time | When we first knew something was wrong |
| Publish date + version | Reports may be revised; version them |
| Next review | Date the partner will receive the corrective-action status update |

> **Why "impact window" matters:** our current reports state duration as "incident declared to closed." In INC-85241 the impact began at 03:01 UTC but the incident was declared at 09:56 UTC. Reporting 7h37m when the true customer-impact window was ~15 hours (bonus issuance to data restoration) reads as minimisation if a partner does the maths themselves. Always let the partner's clock win.

### 3.2 Executive Summary (required, ≤ 250 words)

Exactly four paragraphs:

1. **What happened and the trigger** — one or two sentences, cause-first, with the headline numbers.
2. **Impact** — who, how many, what they experienced, financial/operational consequence in plain terms.
3. **Root cause in one sentence** — comprehensible to a non-engineer.
4. **Resolution and commitment** — when service was restored, the single most important corrective action, and when the partner will hear from us next.

**Good example (based on INC-85241):**

> On 17 March 2026 at 03:01 UTC, a defect in Fast Track's data migration process caused 167,108 player accounts to be marked as unverified. An active lifecycle campaign acted on this incorrect data, crediting a casino bonus to all 167,108 accounts and triggering notification emails to each.
>
> 13,878 of those emails reached players before the email provider blocked all outbound sending, a block that also held back 59 legitimate emails from other campaigns for approximately 10 hours. Your support team handled the resulting player complaints and issued manual goodwill bonuses.
>
> The root cause: the migration file used the text values "true"/"false" where our import expected 1/0, and the import silently converted every value to 0. Our post-migration checks verified record counts but not field values, so the error went undetected until the campaign had already fired.
>
> Correct player data was restored by 15:12 UTC and email delivery by 16:57 UTC via a secondary provider. The primary fix — a field-level validation gate that blocks any import where source and database do not match 100% — ships by [date]. You will receive a corrective-action status update on [date].

**Disqualifiers:** passive voice in paragraph 1; any sentence a commercial director couldn't parse; missing numbers; no next-contact date.

### 3.3 Partner Impact (required)

Quantify from the **partner's perspective**, not the system's. Structure:

- **Players affected** — unique count, what they experienced
- **Financial/bonus impact** — what was credited, exposure, and what reduced it (e.g. "only 8.3% of emails delivered, so most players were unaware of the bonus")
- **Operational impact on the partner** — complaint volume, manual work, reputational handling
- **Collateral impact** — anything beyond the triggering failure (e.g. the 59 legitimate blocked emails). Never bury collateral damage; partners always find it.
- **Metrics table** — every measurable count in one table

**Rules:** Every number must be exact or explicitly approximate ("~137,000"). Resolve every dangling fact — if you write "one user received a duplicate bonus," say why and whether it was corrected. Unexplained loose threads are credibility leaks.

### 3.4 Response Metrics (required — new section)

A short table that makes our response speed transparent and comparable across incidents. This is the section that demonstrates operational maturity better than any prose:

| Metric | Definition | INC-85241 example |
|---|---|---|
| Time to impact | Trigger → first customer impact | 0 min (immediate) |
| Time to detect | First impact → first internal signal | 6h 29m |
| Time to engage | Detection → SOC acknowledgement | 1 min |
| Time to declare | Detection → formal P1 | 1h 26m |
| Time to root cause | Declaration → confirmed root cause | 2h 8m |
| Time to mitigate | Root cause → impact stopped/contained | 2h 54m |
| Time to restore | Detection → full service restoration | ~7h 30m |

Where a metric is bad, **say so in one sentence and point to the corrective action that fixes it.** Example: "Detection took 6.5 hours because no alerting existed on bulk action throughput; AI-06 addresses this." Hiding a bad number is worse than the number.

### 3.5 Timeline (required)

- One table, all times **UTC**, date repeated on day changes
- Every row: timestamp + factual event, ≤ 2 sentences
- Must include: trigger, first impact, detection, partner contact (both directions), declaration, root-cause confirmation, each mitigation step, partner verifications, resolution
- Mark partner-communication rows so reviewers can audit comms latency at a glance (e.g. prefix **[COMMS]**)
- Pre-incident context rows (e.g. "lifecycle created 12 March") are encouraged — they let the reader understand the setup without a separate "lead-up" section

**Disqualifiers:** mixed timezones; gaps longer than 1 hour during active response with no row explaining what was happening; rows that editorialise ("team worked diligently").

### 3.6 Root Cause Analysis (required)

Four subsections, in this order — this is the AWS propagation-path pattern:

**a) What happened (the trigger).** The specific change or action, the mechanism of failure, at the technical depth of: *"The migration used `LOAD DATA LOCAL INFILE` into a temporary table whose boolean columns expected 1/0. The file contained the strings 'true'/'false'. MySQL coerced the non-numeric strings to 0 without raising an error."* Real commands, real field names, real error behaviour. Partners' technical teams read this section; vagueness here destroys the credibility built everywhere else.

**b) The propagation path.** How a local fault became customer impact. Write it as a chain: *incorrect data → active lifecycle consumed it → 167,108 players added in 4 minutes (peak 43,939/min) → 334,216 actions fired in 7 minutes → email provider flagged the volume as abnormal → all partner email blocked.* One chain, each link explicit. If you cannot write the chain in one line of arrows, the analysis isn't finished.

**c) Why it was not caught earlier.** The honesty section. Cover *every* layer that could have caught it and didn't: pre-import validation, post-import verification, monitoring of action throughput, alerting on email volume, the gap between impact (03:01) and detection (09:30). Each miss must map to a corrective action. The Anthropic benchmark here: they explicitly wrote "we relied too heavily on noisy evaluations" — that sentence costs nothing and buys enormous trust.

**d) Contributing factors.** Bulleted, each one a condition that didn't cause the incident but enlarged it (e.g. "active lifecycles meant incorrect data was acted on within hours of import" — a blast-radius observation).

**Method note:** apply five-whys internally before writing, but publish the synthesis, not the Q&A scaffolding.

### 3.7 Mitigation and Recovery (required)

Chronological prose: what stopped the bleeding, what fixed the data, what restored service, who verified what. Two rules:

- **Distinguish hotfix from permanent fix** explicitly ("the hotfix deployed during the incident accepts both formats; the permanent safeguard is the validation gate in AI-01").
- **Show joint verification.** Every "partner confirmed X" line demonstrates we don't self-certify recovery.

### 3.8 Corrective Actions (required)

This is where our current format needs the most upgrade. Required columns:

| ID | Action | Owner (team) | Priority | Due date | Status | Verification criterion |
|---|---|---|---|---|---|---|
| AI-01 | Field-level post-import validation comparing every CSV field against the database; any mismatch blocks go-live. | Engineering | P1 | 2026-04-15 | In progress | A deliberately corrupted test file is rejected by the pipeline in staging; evidence linked. |

Rules:

- **Every action has a due date.** "Committed to making sure this cannot happen again" without dates is a platitude.
- **Verification criterion = how we'll prove it's done**, not a restatement of the action. Prefer "a deliberately injected failure is caught" over "validation implemented."
- **Tag each action by horizon:** *Immediate* (done during incident), *Short-term* (≤ 30 days), *Architectural* (structural, may take quarters). Partners should see we operate on all three.
- **Map actions to RCA gaps.** Every miss named in 3.6c has a corresponding action; every action references the gap it closes.
- **Commit to a status update date** — and put it in the header block.

### 3.9 What This Means for You (required — new section, ≤ 150 words)

Close facing the partner, not the system:

- What's already different today (hotfixes, monitoring live now)
- What changes for their workflows, if anything (e.g. new sign-off gate before imports)
- When they'll hear from us next (corrective-action review date)
- Where to raise questions (named channel)

This converts the report from a confession into a partnership artifact.

### 3.10 Appendices (optional)

Raw delivery logs, affected activity IDs, query outputs, glossary. Anything that serves auditors but would clog the narrative.

---

## PART 4 — QUALITY GATE (AI-AGENT CHECKLIST)

A draft must pass all gates before publication. This list is written so an AI agent can evaluate each item as pass/fail and report what is missing.

**Completeness — facts that must exist:**
- [ ] Impact window (first customer impact → last customer impact), UTC
- [ ] Detection time and detection source (alert / partner report / manual)
- [ ] Exact affected counts (players, actions, emails, bonuses) or explicit approximations
- [ ] Trigger named as a specific change/command/config
- [ ] Propagation chain written as a single arrow sequence
- [ ] Every detection/monitoring layer that failed, listed
- [ ] All seven response metrics computed
- [ ] Hotfix vs permanent fix distinguished
- [ ] Every corrective action has owner, due date, status, verification criterion
- [ ] Every RCA gap maps to ≥ 1 corrective action (and vice versa)
- [ ] Partner verification steps present in timeline
- [ ] Next-update date stated in header and closing
- [ ] No dangling facts (every anomaly mentioned is explained or explicitly marked under investigation)

**Tone — automatic flags:**
- [ ] No passive voice in executive summary paragraph 1
- [ ] No forbidden phrases (Part 2 list)
- [ ] No named or identifiable individuals
- [ ] No minimisers ("briefly," "small number," "may have") attached to quantified impact
- [ ] Single timezone throughout timeline
- [ ] Executive summary ≤ 250 words; readable by a non-engineer (agent test: summarise it for a CEO — if information is lost, it fails)

**Brand voice — Fast Track checks (Part 2B):**
- [ ] UK English throughout (flag: organization, behavior, analyze, apologize, center)
- [ ] "Partner" used, never "customer"/"client"
- [ ] No self-praise ("industry-leading," "world-class," "best-in-class" about Fast Track or its response)
- [ ] No humour or wit anywhere
- [ ] Third-party suppliers named factually, never framed as root cause
- [ ] Product names correct (Fast Track CRM, Fast Track AI, Rewards, Greco, Singularity Model, RTD)
- [ ] Closing section is forward-looking and partner-outcome-framed; factual sections carry no optimistic spin
- [ ] Document design: Inter Tight, official FT colours only, ≤ 2 accent colours, confidentiality footer present

**Consistency — cross-checks:**
- [ ] Every number in the executive summary matches the impact tables
- [ ] Timeline timestamps are monotonic and match durations claimed in metrics
- [ ] Severity classification matches the stated severity definition
- [ ] Affected services in header all appear in the narrative

**Escalation rule for the agent:** if any *Completeness* item cannot be filled from available inputs (incident channel, logs, timeline), the agent must output a "MISSING INFORMATION" list addressed to the incident commander rather than guessing. Fabricated facts in a postmortem are a severity-one documentation failure.

---

## PART 5 — WORKED EXAMPLE: BEFORE / AFTER

Using real text from INC-85241 to show the standard applied.

**Before (current):**
> DURATION: 7 hours 37 minutes (incident declared to closed)

**After:**
> IMPACT WINDOW: 17 Mar 2026 03:01 UTC – 17 Mar 2026 17:31 UTC (14h 30m from first incorrect bonus to verified restoration). Email delivery for unrelated campaigns was blocked 06:00–15:47 UTC.

**Before:**
> The provider is committed to making sure this type of incident cannot happen again. The following actions have been identified and assigned to named teams.

**After:**
> Five corrective actions are in progress, each with an owner, due date, and verification criterion below. Three address the import pipeline directly; two address the detection gaps that delayed our response by 6.5 hours. We will send you a written status update on each action on 15 April 2026.

**Before (detection, implicit):**
> The Provider SOC received an alert that 2 emails were not delivered…

**After (explicit honesty, new in RCA 3.6c):**
> The campaign fired 334,216 actions in seven minutes at 03:01 UTC, yet our first signal arrived at 09:30 UTC — and it was an alert about two undelivered emails, not the mass send itself. We had no alerting on bulk action throughput or abnormal email volume. A campaign 100x normal size should page us within minutes, not surface as a side effect six hours later. Corrective action AI-06 introduces throughput anomaly alerting on the action pipeline.

---

## PART 6 — PROCESS NOTES

- **Internal vs partner version:** the internal postmortem may contain partner-identifying details, personnel context, and commercial discussion. The partner version is derived from it, never the reverse. Same facts, same numbers — redaction only, no re-narration.
- **Publication SLA:** preliminary summary within 48 hours of resolution; full report within 5 business days; revised versions are versioned and change-logged.
- **Review chain:** author (IC or SOC Team Lead) → Head of SRE → CTO for P1s → publish. AI agent runs the Part 4 gate before each human review.
- **Action follow-through:** corrective actions are tracked in the incident tooling; the next-review date in the header is a calendar commitment, not decoration. A postmortem whose actions silently expire is worse than no postmortem.
