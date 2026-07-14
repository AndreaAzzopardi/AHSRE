# Incident Handling Guidelines — Management Expectations

Distilled from Slack conversations between Patrik Potocki (CTO) and Andrea Azzopardi
(Head of SRE) — primarily the direct DM (`D084SQ7KNHX`) and the private
`#patrik_andrea_gerald_notes` channel (`C0AV1CKLG58`) — covering March–July 2026.

These are the principles every active incident is judged against by the
management-attention agent (`agents/management-attention-agent.md`). Each principle
cites its source conversation. When a principle and an incident runbook conflict,
raise it — do not silently pick one.

---

## A. Ownership & control

**A1. Every incident has an owner and Head-of-SRE-level visibility.**
"You're accountable for every single incident… you don't need to look [at] every
incident but at least have the processes so you are aware of what's happening."
— Patrik, 9 Jul 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783594195662759))

**A2. No incident is "just closed".**
Every problem gets an action addressing why it broke. "We have SO many problems and
feels like they just getting 'closed', no action point… the teams need to get action
to them." — Patrik, 14 Apr 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1776159589417019));
reinforced 9 Jul: "there is always an action to fix why it broke".

**A3. "It's just 10/30 minutes" is never an acceptable rationale.**
Minutes of integration delay are real partner impact. "~60% [of slow-processing
alerts] are just closed by SOC but that means usually minutes of delays in the
integration just ignored… just ignoring is completely the wrong approach."
— Patrik, 9 Jul 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783594195662759))

**A4. Recurring problems are escalated to the owning team for a long-term fix,**
not re-closed each time. — Patrik, 9 Jul + 14 Apr 2026; also the bet-at-home daily
queue-buildup note (Andrea, 4 Jun 2026, #patrik_andrea_gerald_notes): trend analysis
should have identified the recurring pattern earlier.

## B. Escalation & timeliness

**B5. Escalate early — not after hours without recovery.**
Rolletto: alarms from 01:00, investigation started 01:50, escalation only at 03:30 —
"we should have escalated earlier given the state of the system" (Andrea, 25 Apr
2026, #patrik_andrea_gerald_notes). Winspirit: "The right thing would have been to
1. Escalate to SRE already last night 2. Try to fix…" — Patrik, 14 May 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1778738069655819))

**B6. Security incidents are P1 until de-escalated.**
"All security Incident should be P1 until otherwise decided." Flow: SOC → SRE →
Patrik/Andrea → security team (Max/Agustín) — only ping the security team when it's
actually on fire. — Patrik, 12 May 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1778569848399589))

**B7. Critical-path failures are top priority.**
A crashing pod "means our system is down in some area" — critical alerting and the
incidents behind it cannot wait. — Patrik, 8 Jul 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783498752259209))

**B8. Night and handover incidents must not be lost.**
Anything from a late/night shift needing SRE follow-up gets explicitly assigned
(ClickUp/SRE board), not just mentioned in the handover text. — Andrea, 30 Apr 2026,
#patrik_andrea_gerald_notes.

## C. Partner communication

**C9. Inform partners fast, even before root cause is known.**
"When a service is clearly not working, even if we don't know the root cause we
always recommend we inform the partner about it as to be proactive. We should not
wait for the SRE to remind us." (Andrea, 15 May 2026). 40 minutes on a basic,
templated alarm was called out as too slow (TurboSMTP, 7 May); 2 hours is a clear
failure (Play slow-processing, 25 May). — #patrik_andrea_gerald_notes.

**C10. Close the loop.**
Recovery/resolution comms go out when the issue clears (bet-at-home queue cleared at
03:00 with no follow-up, 4 Jun), and partner follow-up questions get answered
(Tuohi resolution comms 4+ hours late and unanswered questions produced a partner
complaint ticket, 25 Jun). — #patrik_andrea_gerald_notes.

**C11. Comms are accurate and crystal clear on impact.**
Correct timestamps, no template placeholders or internal notes pasted into partner
messages, and plain impact statements — "make it crystal clear that NO emails at all
are going out" (Patrik, 14 May 2026,
[source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1778738110931629)).
Wording examples: 11/15/25 May notes in #patrik_andrea_gerald_notes.

## D. Handling quality

**D12. Informed decisions over passive waiting.**
Mitigate what you can; assess business impact before destructive actions
(purging/skipping); "if we don't feel confident then yes we need to wait" — but say
so explicitly. — Patrik, 14 May 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1778738069655819))

**D13. Runbooks followed, basic checks done.**
The canonical failure (Roobet, 8 May 2026): "Checks very basic… No partner
information, no escalation, runbook not followed. I had to notice this myself during
my usual checks." — Andrea, #patrik_andrea_gerald_notes.

**D14. Don't close while partner-side work remains open.**
"Do not close the incident after the hotfix has been applied. Since we need to work
with Partner until they resolve their integration." (Happy-Ending, 8 May 2026,
#patrik_andrea_gerald_notes)

**D15. The incident record is self-contained.**
Summary and updates must be understandable from a phone; a bare Intercom link is not
enough — "when checking on the phone is super hard to understand what the problem
is." — Patrik, 13 Jul 2026
([source](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783927410061179))

## E. The questions every digest must answer

**E16.** Patrik's literal recurring check-in questions (3, 5, 6 Jul 2026):

> "just see so everything is under control in terms of incidents" ·
> "anything urgent going on or just smaller things?" ·
> "just so we don't have any new bugs" ·
> "like 50+ open so feels we need to spend this week to clean up"

Every management-attention digest leads with: **under control? · urgent vs smaller? ·
new since last run? · total open (with trend).**
([3 Jul](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783072239622149) ·
[5 Jul](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783280672575939) ·
[6 Jul](https://fasttrack-solutions.slack.com/archives/D084SQ7KNHX/p1783345072041649))
