# Incident Report INC-14303

| Field | Value |
|---|---|
| **Incident ref** | INC-14303 |
| **Client environment** | All Fast Track CRM client environments (all brands) |
| **Date of incident** | 16 July 2026 |
| **Report date** | 16 July 2026 |
| **Severity / Status** | P1 (Critical) throughout; login restored and verified by 10:16 UTC, 16 July 2026; supplier platform incident resolved 10:44 UTC; the Provider's incident in Monitoring as of the report date — corrective actions open pending the supplier's root-cause report |
| **Classification** | Confidential – shared between the Provider and the Client |

On 16 July 2026 from 08:00 UTC, WorkOS, the third-party authentication provider used by Fast Track CRM, experienced elevated error rates and latencies across its platform — the window the supplier confirmed in its resolution notice. Authorisation requests from the CRM login page to the WorkOS authentication endpoint timed out after approximately 30 seconds, making new CRM logins unavailable across all brands. The fault originated entirely on the supplier's platform; no change was deployed by the Provider. The Provider identified the failing logins internally and declared incident INC-14303 at 08:13 UTC — thirteen minutes after the supplier-confirmed onset and thirteen minutes before the supplier's public status page first acknowledged the outage at 08:26 UTC.

The impact was confined to the authentication step for new sessions. Users who were already logged in were unaffected unless they logged out, and the core CRM engine does not depend on the authentication provider once a session is established — all lifecycles, activities and send-outs executed as scheduled throughout, and no campaign was halted. At 08:31 UTC the Provider published an in-app banner informing users on the CRM login page of the issue, and at 08:33 UTC extended it to advise already-logged-in users not to log out, as a deliberate session-preservation measure. WorkOS reported at 10:11 UTC that it had identified the root cause and implemented a fix; successful logins were observed from 10:09 UTC, and restoration was verified across environments — including email-code (magic link) sign-in, whose queued verification emails were delivered — by 10:16 UTC. The Provider confirmed restoration to clients at 10:19 UTC, and WorkOS declared its platform incident resolved at 10:44 UTC, stating that the elevated error rates and latencies occurred between 08:00 and 10:10 UTC.

No further impact was observed following restoration. A separate incident at the supplier affecting email delivery later the same day (12:06 UTC → 12:21 UTC, resolved by the supplier) produced no reported renewed impact on CRM logins. The Provider's incident remains in a monitoring state pending the supplier's full root-cause report.

## Incident Overview

- **Primary impacted systems:** Fast Track CRM login (new session authentication) on all brands.
- **Not affected:** existing logged-in sessions; the core CRM engine — all lifecycles, activities and send-outs ran as scheduled; no campaign was halted; no data loss.
- **Origin:** elevated error rates across the WorkOS platform, the third-party authentication provider through which all CRM logins are routed, caused authorisation requests to time out.
- **Impact window — CRM login:** 08:00 UTC, 16 July 2026 → 10:16 UTC, 16 July 2026 (2h 16m; first successful logins from 10:09 UTC; supplier-stated error window 08:00 → 10:10 UTC). Email verification codes issued during the window were queued at the supplier and delivered on restoration.
- **Detection method:** the Provider detected the failure internally and declared the incident at 08:13 UTC, before the supplier's status page reflected the outage (08:26 UTC). Monitoring of the login flow relied on manual checks during the incident (addressed under CA-03).
- **Severity / Status:** P1 (Critical) throughout; supplier platform incident resolved 10:44 UTC; the Provider's incident in Monitoring as of the report date.

## Root Cause Analysis

Fast Track CRM delegates operator authentication to WorkOS, a third-party identity provider. The authentication step is an availability dependency for establishing new sessions only: it holds no CRM client data, campaign data, or player data, and the CRM application does not call it again once a session exists. The failure mode was unavailability — timeouts — not corruption, so no data handled by the CRM was at risk. No client data was altered or exposed.

From 08:00 UTC, requests to the WorkOS authorisation endpoint (`api.workos.com/user_management/authorize`) timed out after approximately 30 seconds, so users on the CRM login page on every brand could not establish a session. The Provider confirmed the fault was at the supplier by reproducing the timeout directly against the supplier's API while the supplier's status page still showed all systems operational, and contacted the supplier through the shared support channel at 08:22 UTC. WorkOS acknowledged elevated platform-wide error rates at 08:26 UTC, identified the root cause and implemented a fix by 10:11 UTC, completed deployment at 10:30 UTC, and declared the incident resolved at 10:44 UTC, confirming that the elevated error rates and latencies occurred between 08:00 and 10:10 UTC. The supplier has not yet published the underlying mechanism; this report will be updated when its root-cause report is received (CA-01).

During the outage the Provider evaluated switching brands to Google sign-in as a fallback. This was not applied: the switch requires a CRM API restart per brand and would only serve accounts that had previously linked Google sign-in, so it could not have restored access for most affected users before the supplier's fix landed (addressed under CA-02).

- **Key enabler:** all CRM brand logins route through a single third-party authentication provider, with no fallback sign-in path that can be enabled without a service restart.
- **Contributing factor:** the supplier's status page lagged actual impact by 26 minutes, and login-flow health was verified manually rather than by automated monitoring.
- **Mitigation:** the supplier identified and deployed a fix on its platform; the Provider preserved existing sessions via in-app guidance and confirmed restoration across environments before issuing client communications. Fallback sign-in options (CA-02) and synthetic login monitoring (CA-03) are open corrective actions.

## Impact Assessment

- **Availability — CRM login:** unavailable on all brands from 08:00 UTC to 10:16 UTC, 16 July 2026 (2h 16m). Client teams on the CRM login page could not establish new sessions; six clients contacted Partner Support during the window. Recovery was progressive from 10:09 UTC — two brand environments remained unavailable at 10:12 UTC before full restoration was verified at 10:16 UTC.
- **Existing sessions:** users already logged in retained full CRM access throughout, unless they logged out. In-app guidance advising against logging out was published at 08:33 UTC.
- **Campaign execution / core operations:** the core CRM engine does not depend on the authentication provider after session establishment — all lifecycles, activities and send-outs ran as planned; no campaign was halted.
- **Data integrity:** the affected component performs authentication only and holds no CRM client, campaign, or player data; the failure mode was timeout, not corruption. Email verification codes queued during the outage were delivered on restoration. No client data was altered or exposed.
- **Collateral impact:** none identified beyond the login unavailability described above. A separate supplier incident affecting email delivery occurred later the same day (12:06 UTC → 12:21 UTC, resolved by the supplier); no renewed impact on CRM logins or login verification emails was reported to the Provider.

## Timeline of Key Events (UTC)

*Rows marked [COMMS] are communications between the Provider and the Client.*

| Timestamp (UTC) | Action | Description |
|---|---|---|
| 2026-07-16 08:00 | Supplier fault | Elevated error rates and latencies began on the WorkOS platform (onset confirmed in the supplier's resolution notice); CRM authorisation requests began timing out. |
| 2026-07-16 08:13 | Incident declared | INC-14303 declared at P1 (Critical); response team assembled. |
| 2026-07-16 08:14 | Origin identified | Requests to the WorkOS authorisation endpoint confirmed to time out after ~30 seconds; fault isolated to the supplier's API. |
| 2026-07-16 08:15 | Scope confirmed | Supplier's public status page still showed all systems operational; direct API reproduction confirmed the fault was at the supplier. |
| 2026-07-16 08:22 | Supplier contacted | The Provider raised the issue with WorkOS through the shared support channel. |
| 2026-07-16 08:26 | Supplier acknowledgement | WorkOS status page acknowledged elevated error rates across its platform. |
| 2026-07-16 08:31 | [COMMS] Client informed | In-app banner published informing users on the CRM login page that login was unavailable due to a third-party provider issue. |
| 2026-07-16 08:33 | Precautionary measure | Banner guidance extended to already-logged-in users advising them not to log out, preserving active sessions. |
| 2026-07-16 09:01 | Status check | Issue confirmed still ongoing; supplier still investigating. |
| 2026-07-16 ~10:04 | [COMMS] Client contact | Six clients had contacted Partner Support; updates requested. |
| 2026-07-16 10:05 | Fallback evaluated | Switching brands to Google sign-in considered; not applied — requires a CRM API restart per brand and serves only previously-linked accounts. |
| 2026-07-16 10:09 | Recovery observed | First successful logins observed. |
| 2026-07-16 10:11 | Supplier fix reported | WorkOS reported root cause identified, fix implemented, error rates decreasing. |
| 2026-07-16 10:12 | Partial recovery | Recovery confirmed progressive; two brand environments still unavailable. |
| 2026-07-16 10:16 | Restoration verified | Logins verified across environments, including email-code (magic link) sign-in; queued verification emails delivered. |
| 2026-07-16 10:19 | [COMMS] Client informed | Client communications sent confirming login was working again. |
| 2026-07-16 10:26 | Status change | Incident moved from Investigating to Monitoring; severity remained P1. |
| 2026-07-16 10:30 | Supplier deployment | WorkOS completed deployment of its fix and moved to monitoring its systems. |
| 2026-07-16 10:44 | Supplier resolution | WorkOS declared its platform incident resolved, confirming elevated error rates and latencies between 08:00 and 10:10 UTC. |
| 2026-07-16 12:06 | Supplier fault (separate) | WorkOS reported a separate incident: delays in email delivery. No renewed impact on CRM logins was reported to the Provider. |
| 2026-07-16 12:21 | Supplier resolution | WorkOS resolved the email delivery delays. |

## Containment and Remediation Measures

- Isolated the fault to the supplier's authorisation endpoint by direct reproduction at 08:14 UTC, before the supplier's status page reflected the outage, and raised it with the supplier through the shared support channel at 08:22 UTC.
- Published an in-app banner at 08:31 UTC informing affected users, and extended it at 08:33 UTC to advise logged-in users not to log out — a deliberate measure that preserved active sessions and limited the impact to new logins only.
- Evaluated a fallback to Google sign-in during the outage; deliberately not applied, as it required per-brand service restarts and would not have served most affected users.
- Verified restoration across environments — including email-code sign-in and delivery of queued verification emails — before confirming resolution to clients at 10:19 UTC.
- The permanent fix was deployed by the supplier on its platform at 10:30 UTC; the corrective actions below address the Provider's own dependency and detection posture.

| ID | Action | Owner (team) | Due date | Status |
|---|---|---|---|---|
| CA-01 | Obtain and review the supplier's root-cause report for the 16 July platform outage; update this report with the confirmed cause | SRE | 30 July 2026 | Open |
| CA-02 | Review fallback sign-in options so that an alternative login path can be enabled without per-brand service restarts | CRM Engineering | 14 August 2026 | Open |
| CA-03 | Add synthetic monitoring of the CRM login flow so authentication failures alert automatically rather than relying on manual checks | SRE | 14 August 2026 | Open |

## Next Steps

- Continued monitoring of login health across all client environments following the supplier's fix.
- Review of all third-party service dependencies in the CRM login and session path to confirm each has an automated detection route and a documented fallback, extending the lesson of this incident beyond the authentication provider.
- A written status update on the open corrective actions will be provided by 31 July 2026.
- Questions are welcome through the Client's usual contact at the Provider, or the Provider's Head of SRE, who owns this report.

*This document is confidential and shared solely between the Provider and the Client for the purpose of incident review and remediation. It must not be distributed, reproduced, or disclosed to any third party without prior written consent. Findings reflect the Provider's assessment as of the report date and may be updated if new information becomes available.*

---

<!-- INTERNAL AUTHOR'S NOTE — remove before publication.

MISSING INFORMATION (for the incident commander):
1. [RESOLVED in v3] Onset of impact — now 08:00 UTC, taken from WorkOS's resolution notice ("elevated error rates and latencies between 8am and 10:10am UTC"). Impact window updated to 08:00 → 10:16 UTC (2h 16m).
2. Initial detection route — the channel does not show whether the first report came from an internal user, Partner Support, or a client. Currently worded as "detected internally"; correct if a client reported first (that would also require a detection CA cross-reference per the standard).
3. Underlying supplier root cause — WorkOS resolved the incident (10:44 UTC) but has only published the error window, not the mechanism. CA-01 stands.
3b. Separate WorkOS "Email delivery delays" incident (12:06–12:21 UTC) included with "no renewed impact reported" — confirm with Partner Support that no login-code complaints arrived in that window.
4. Corrective-action owners and due dates (CA-01/02/03) and the 31 July status-update date are the author's proposals — confirm before publication. CA-02/CA-03 are inferred from the channel discussion (Google sign-in feature flag requiring CRM API reboot; manual status checks) but were not formally agreed in the channel.
5. Incident still in Monitoring at report time — not yet Resolved. Header status must be updated at closure.
6. "Two brand environments still unavailable at 10:12 UTC" genericises specific brand names mentioned internally (this is an all-clients report; naming other clients' brands would breach confidentiality).
7. One client reported not receiving login verification codes at 10:14 UTC; codes were confirmed delivered (supplier email backlog). Folded into the 10:16 restoration-verified row.
-->
