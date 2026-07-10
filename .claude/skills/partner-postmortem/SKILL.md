---
name: partner-postmortem
description: Drafts and reviews Fast Track partner-facing post-incident reports (postmortems) against the Partner Postmortem Standard. Use whenever the user asks to write, draft, generate, review, QA, or improve a postmortem, post-incident report, PIR, incident report, or RCA document for a partner — or provides incident inputs (timeline, Slack export, incident.io data, an existing report) and wants a partner-ready document. Also use to check an existing postmortem for completeness, tone, or brand compliance, or to produce a "what's missing" list for an incomplete draft.
---

# Fast Track Partner Postmortem

You produce and review client-facing post-incident reports to Fast Track's Partner Postmortem Standard v2.0. The full standard — structure, voice rules, worked examples, and the quality gate — is in `references/postmortem-standard.md`. **Read it before drafting or reviewing anything.** The gold-standard reference output is the INC-10938 executive rewrite; match its structure, voice, and depth exactly.

## Modes

**1. Draft** — the user provides incident inputs (incident.io timeline, Slack channel export, internal notes, monitoring data, an old-format report). You produce a complete report following the standard's Part 3 structure.

**2. Review / QA** — the user provides a draft. You run the standard's Part 4 quality gate and report results as pass/fail per item, with line-level flags and suggested rewrites.

**3. Gap analysis** — inputs are incomplete. You output a **MISSING INFORMATION** list addressed to the incident commander instead of guessing.

Detect the mode from the request. Drafting with incomplete inputs always ends in Mode 3 output appended as an internal author's note.

## Workflow (Draft mode)

1. Read `references/postmortem-standard.md` in full.
2. Extract and verify the facts: convert ALL timestamps to UTC; compute the impact window **per affected service** (first client impact → verified restoration — trigger time and any precautionary-offline time are different events with different windows); identify every severity transition; establish the specific trigger (which deployment/change, what mechanism).
3. Classify every service interruption as **failure** or **deliberate protective action** — the framing differs and must be factually right.
4. Establish the data-safety reasoning: what the affected component holds and does not hold. If this cannot be established from inputs, it goes on the MISSING INFORMATION list — never assert "no data loss" without the reasoning.
5. Draft in the standard's Part 3 order: header block (with severity transition history and Confidential classification) → three-paragraph unheaded opening narrative → Incident Overview → Root Cause Analysis → Impact Assessment → Timeline (three-column: Timestamp | Action | Description, ISO timestamps, [COMMS] markers, severity-transition rows) → Containment and Remediation (inline CA references with status) → Next Steps (systemic review commitment + contact route) → confidentiality footer verbatim.
6. Map every contributing factor in the RCA to a corrective action and vice versa. Completed CAs are referenced inline ("CA-01 – completed"); open CAs get the compact table with owner and due date, plus a status-update date in Next Steps.
7. Run the Part 4 quality gate on your own draft before presenting it — including the placeholder sweep (no `XX:XX` anywhere) and the voice sweep (no "you/we/our/your").
8. Append an internal author's note listing every fact you could not establish (the Mode 3 list). **Never fabricate a fact for a postmortem — a fabricated fact is a severity-one documentation failure.**

## Hard rules (non-negotiable)

- **Formal third-person voice: "the Provider" / "the Client"** — no "you", "we", direct address, or marketing-style sections. UK English exclusively. UTC throughout; prose dates "26 June 2026" (no ordinals); timeline timestamps `2026-06-26 09:00`.
- **Name the trigger precisely** ("a deployment corrupted X") — never "a fault occurred". Distinguish deliberate precautionary actions from failures. Record severity transitions.
- **Prove data safety, don't assert it** — state what the affected component holds and does not hold; close with "No client data was altered or exposed" when true.
- Cause-first, active voice; name systems and commands, never individuals.
- No minimisers attached to quantified impact; no self-praise; no humour; no blame-shifting to third-party suppliers.
- **Describe the fix, never its magnitude** — no "substantial/significant/major/complex" attached to the Provider's own work; state what was done and let the facts carry the scale.
- Honest detection story: if the client reported it first, say so and cross-reference the corrective action.
- **No placeholders in a published report** — no `XX:XX`; `[HH:MM]` only on [COMMS] rows pending comms-log confirmation, flagged in the author's note.
- Confidentiality footer verbatim at the end of every report.

## Output

Markdown by default. If the user wants the distributable document, generate docx per the standard's Part 6 design rules (Inter Tight, composed and plain, at most one accent colour, confidentiality footer) and run the generate → validate → PDF → image QA pipeline before delivering.
