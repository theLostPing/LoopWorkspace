# custom_patches/

Brian's submodule patches, applied at build time by the **Customize Loop** step in
`.github/workflows/build_loop.yml`.

## Why this directory exists and not `patches/`

Upstream's own `patches/` block applies its glob **without** `--directory`:

```bash
git apply ./patches/* --allow-empty -v --whitespace=fix
```

These patches touch files **inside git submodules** (`Loop/`, `LoopKit/`,
`NightscoutService/`), so each one has to be applied with an explicit
`--directory=<submodule>`. That is the route proven to work in this workflow by the
2026-09-16 toolbar fix (build 19). Mixing them into `patches/` would break them.

Leaving `patches/` untouched also keeps upstream's file exactly as upstream has it,
so it can never conflict on a sync.

## What is here

| Patch | Submodule | What it does |
|---|---|---|
| `loopkit-remote-pod-alert-ack.patch` | `LoopKit` | Adds `acknowledgeRemotePodAlerts()` to `RemoteActionDelegate`, with a default protocol-extension implementation so every other conformer still compiles. |
| `nightscoutservice-remote-pod-alert-ack.patch` | `NightscoutService` | Carries the `acknowledge-pod-alerts` remote command end to end: `Action` case, `PodAlertAcknowledgeRemoteNotification`, dispatch, response `CommandType`. |
| `loop-remote-pod-alert-ack.patch` | `Loop` | Implements it on `ServicesManager` — looks up unacknowledged `Omnipod-Dash` alerts, filters to the advisory allowlist, and acknowledges each. |

New Swift types are deliberately added **inside existing files**. A new `.swift`
file would need an edit to the submodule's `.xcodeproj` or it simply would not be
compiled.

## Safety boundary (read before touching the allowlist)

The alerts still **fire**, unchanged. This feature only *acknowledges* an alert that
has already fired — the same call the on-screen acknowledgement button makes.

The allowlist in `Loop/Managers/ServicesManager.swift` is the entire safety property:

```
userPodExpiration    slot3  pod expiration reminder
podExpiring          slot7  pod expired
podExpireImminent    slot2  shutdown imminent (advisory)
lowReservoir         slot4  low reservoir
```

Everything else is excluded by omission (`suspendInProgress`, `suspendEnded`,
`finishSetupReminder`, `unexpectedAlert`, `timeOffsetChangeDetected`). Pod **faults**
— occlusion, pod fault, the real 80-hour auto-off shutdown — are
`PodCommsError.podFault` and never become a `PumpManagerAlert` at all, so they are
unreachable from this code path under any input.

**Widening that list is a therapy-safety decision, not a refactor.**

## Maintenance: these patches ROT

Unlike the `sed` customizations, a patch carries context lines. When upstream edits
one of the six patched files near an anchor, `git apply` fails and **the whole build
fails** — loudly, on purpose, rather than shipping a silently missing feature.

Generated against these submodule pins:

| Submodule | Pin the patch was generated from |
|---|---|
| `Loop` | `7bb17492288f6a6ea76e427277e2d82661dd0a3e` |
| `LoopKit` | `915f58309ff61b6def4981df09dfd96e40bc50af` |
| `NightscoutService` | `2cef4896f0704fb112575ab34b596ee7de78e48d` |

**At each upstream sync**, if a `git apply` here fails, regenerate the patch against
the new pin rather than forcing it. The drift guard in **Verify Customizations**
(`acknowledgeRemotePodAlerts`, `acknowledge-pod-alerts`,
`remoteAcknowledgeablePodAlertIdentifiers`) is the backstop that catches a patch that
applied only partially.

## Wire format

Nightscout remote command payload — no OTP required, matching `cancel-temporary-override`:

```json
{ "acknowledge-pod-alerts": "1", "remote-address": "<address>", "sent-at": "<iso8601>" }
```

Returns `commandType: acknowledge_pod_alerts`. If nothing clearable is outstanding it
fails with "No pod alerts to clear" rather than reporting a false success.
