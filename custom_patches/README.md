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
| `loop-remote-pod-alert-ack.patch` | `Loop` | Implements it on `ServicesManager` — looks up unacknowledged Omnipod alerts, filters to the advisory allowlist, acknowledges each; **and** makes `AlertManager.acknowledgeAlert` dismiss an already-presented in-app modal. |
| `loop-timesensitive-ack.patch` | `Loop` | Lifts non-critical alerts to Time Sensitive (upgrade only), switches on the Acknowledge notification button upstream left commented out, makes the four remote bolus/carb notices Time Sensitive, and routes the button through `acknowledgeAlertAwaitingDevice`. |
| `apply_whats_new.py` (script, not a patch) | `Loop` | Personal version (`BrianBuild.version`) plus a once-per-version What's New sheet on first launch after an update, re-openable from Settings. |

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

## 2026-11-01 fix — read this before touching the manager id

This shipped on 10/29 querying one hardcoded `"Omnipod-Dash"`, which matched **nothing**, so every
remote ack answered "No pod alerts to clear" while a Pod Expiration Reminder sat on screen.

**This workspace builds `OmnipodKit` (loopandlearn/OmnipodKit)** — the single merged Omnipod
submodule on `dev` — and its `OmniPumpManager.pluginIdentifier` is **`"Omni"`**. It is not
OmniBLE (`"Omnipod-Dash"`, model `"Dash"`) and not OmniKit (`"Omnipod"`, model `"Eros"`).

⚠️ The mistake worth not repeating: `.gitmodules` was read from the **default branch**, which
lists OmniBLE/OmniKit/DanaKit. `dev` has an entirely different submodule set. Always pin the ref,
and confirm with `git ls-tree origin/dev`. Independent check: Nightscout `pump.model` is
`"Omnipod 5"`, which only `OmnipodKit` can produce (`state.podType.description`).

The code now queries **all three** identifiers rather than one guess. That is safe because the real
safety gate is the four-identifier allowlist, which is byte-identical across all three plugins.

**Second fix, independent:** `AlertManager.acknowledgeAlert` never reached `modalAlertScheduler`
(only `retractAlert` does), so a remote ack left the in-app modal on screen. It now calls
`removePresentedAlert` on the **main queue** (`clearPresentedAlert` has a `dispatchPrecondition`).
That is a no-op on the tap path, because `InAppModalAlertScheduler.show()` clears
`alertsPresented` *before* calling back. Do **not** use `unscheduleAlert` there (it cancels pending
timers and would break `suspendEnded`'s 15-minute repeat) or `retractAlert` (it writes a false
retraction into the alert store).

## Versioning: why the marketing version does NOT change

Standing rule (11/01/26): every release ships a real user-visible version and a What's New.

This is a **fork**, so `CFBundleShortVersionString` deliberately stays equal to the UPSTREAM Loop
release it is built from. That number is what the Loop community, Loop's diagnostics and Nightscout
all read; inventing a value there would misreport which Loop is running on a medical device.

⚠️ It would also break the pod-alert gate. Nightscout's `loop.version` is literally
`"<marketing>.<build>"`, and Warden compares it with PHP `version_compare`. Measured:

```
version_compare("3.14.11-tlp.1.25", "3.14.11.24", "<")  ->  TRUE   (gate refuses forever)
version_compare("3.14.11.25",       "3.14.11.24", "<")  ->  false  (gate opens)
```

An unknown alphabetic segment sorts BELOW a plain number, so a `-tlp.N` marketing version jams the
gate shut. The personal version lives in `BrianBuild` in `Loop/Views/SettingsView.swift` instead.

**On every release: bump `BrianBuild.version` and replace `BrianBuild.whatsNew`.** One short plain
line per item. The build number comes from TestFlight+1 automatically; it is not in the repo.

## Why What's New is a SCRIPT and not a patch

It was a patch, and it failed four builds with `patch does not apply` at
`SettingsView.swift:50` -- while the byte-identical patch applied to the byte-identical pinned
blob locally, with the same flags. Whitespace flags were blamed twice and were not the cause.

The cause: **`basal_lock`**, one of the Loop and Learn customizations run earlier in the same
step, adds a Preferences feature that inserts `case preferences` directly after
`case favoriteFoods` -- exactly where the patch anchored -- plus 15 more lines in that file. The
runner's `SettingsView.swift` is 716 lines by the time the patch runs; the pinned blob is 700.
A context diff generated against the pristine blob can never apply.

Found by instrumenting the runner (`shasum`, `wc -l`, `git -C Loop diff --stat`) rather than by
more guessing. **If a patch fails where the blob says it should not, dump the file's hash and
line count on the runner first** -- an earlier customization is the usual answer.

`CustomizationSelect.sh` is fetched live from `loopandlearn/lnl-scripts@main` and is NOT pinned,
so its output can change again at any time. `apply_whats_new.py` therefore makes anchored
single-string edits that do not depend on surrounding context, and exits non-zero if any anchor
is missing or ambiguous.

## Maintenance: these patches ROT

Unlike the `sed` customizations, a patch carries context lines. When upstream edits
one of the six patched files near an anchor, `git apply` fails and **the whole build
fails** — loudly, on purpose, rather than shipping a silently missing feature.

Generated against these submodule pins:

| Submodule | Pin the patch was generated from |
|---|---|
| `Loop` | `813f07cb18bf0d31c2dbd720b68703e454d9691e` |
| `LoopKit` | `a7b43f4d8e3cfcafe287c96303be13aff23492cd` |
| `NightscoutService` | `2cef4896f0704fb112575ab34b596ee7de78e48d` |

Re-verified against these pins on 2026-11-12 (upstream 3.14.12 sync) by actually
running them, not by reading a file list: all three patches pass `git apply --check`;
the three Loop and Learn customizations still resolve (`basal_lock` ->
`dev_basal_lock.patch`); all four `sed` source strings still match, including
`with U-100 Insulin` in OmnipodKit's `PairPodView.swift`, which was the one at real
risk because that pin moved; and `apply_whats_new.py` was run end to end on a tree
with the customizations already applied, because upstream changed
`StatusTableViewController.swift` (+58/-8) and it is one of the script's two targets.

**At each upstream sync**, if a `git apply` here fails, regenerate the patch against
the new pin rather than forcing it. The drift guard in **Verify Customizations**
(`acknowledgeRemotePodAlerts`, `acknowledge-pod-alerts`,
`remoteAcknowledgeablePodAlertIdentifiers`) is the backstop that catches a patch that
applied only partially.

## 2026-11-16 (personal 1.1.0) - Time Sensitive + the Acknowledge button

Three voice actions, each approved with Face ID from the car
(`a-77b8d4891a1e1891334eb5c3`, `a-63c58eadfc4cabde345d7b74`,
`a-5e2091207c70212f97ee952f`).

**The entitlement was already there.** `com.apple.developer.usernotifications.time-sensitive`
ships in upstream `Loop.entitlements` and was already in build 27. Nothing was added
and no App ID capability was changed - the `identifiers` lane in `fastlane/Fastfile`
does not manage one, and does not need to. Loop simply never *used* `.timeSensitive`.
There is now a drift guard asserting the entitlement is present, so if upstream ever
drops it the build fails loudly rather than shipping notices iOS will quietly demote.

**CarPlay: this does NOT put Loop in the CarPlay bottom bar, and cannot.** Only
Apple's Reminders, News and Home break through to the CarPlay screen from their
iPhone counterparts; the per-app *Show in CarPlay* toggle exists only for those and
for apps that are themselves CarPlay apps. Loop has no CarPlay entitlement or scene,
and Apple grants that only to specific app categories. What this build does buy:
breaking through Focus/Driving Focus, eligibility for **Announce Notifications** (Siri
reads them aloud through CarPlay - the real hands-free path), and acknowledging from
the Lock Screen without unlocking.

**The Acknowledge button was 95% upstream already.** `Action.acknowledgeAlert`, the
`LoopNotificationCategory.alert` category and the handler at `LoopAppManager.swift`
all existed; `UserNotificationAlertScheduler.swift` just never set
`categoryIdentifier`, behind *"TODO: Once we have a final design and approval for
custom UserNotification buttons"*. This switches it on.

Two deliberate departures from upstream:

* **`options: []` instead of `.foreground`.** Mirrors Warden's Approve/Deny, which are
  the HA Companion pattern and handle the tap in the background. `.foreground` would
  force the phone open, defeating the entire point.
* **Routed through `acknowledgeAlertAwaitingDevice`, not `acknowledgeAlert`.** The
  upstream call records the acknowledgement outside the responder's completion
  handler, so a tap taken with the pod out of range marks the alert done though the
  pod never cleared it - the poisoning bug of 2026-11-04. A button pressed from a
  moving car is precisely when the pod is least likely to answer.

**Never downgrades.** The `.active -> .timeSensitive` lift happens in one place, and
`.critical` and `.timeSensitive` return unchanged, so no alert can be made quieter.
It is done at that choke point rather than by matching pump/CGM manager identifiers,
so it covers every non-critical Loop notice - slightly broader than "device alerts",
and the right trade, because hardcoding a manager id is exactly what shipped the pod
ack broken on 2026-10-29.

Scope note: Loop has **no** remote *override* notification - only remote bolus and
carbs plus their two failure notices. All four are now Time Sensitive.

## Wire format

Nightscout remote command payload — no OTP required, matching `cancel-temporary-override`:

```json
{ "acknowledge-pod-alerts": "1", "remote-address": "<address>", "sent-at": "<iso8601>" }
```

Returns `commandType: acknowledge_pod_alerts`. If nothing clearable is outstanding it
fails with "No pod alerts to clear" rather than reporting a false success.

## 2026-11-12 (personal 1.0.2) - the outcome is now TRUTHFUL

v1.0.1's blind fallback reported **success** when it had done nothing at all.
`OmniPumpManager.acknowledgeAlert` opens with

```swift
guard self.hasActivePod, !state.activeAlerts.isEmpty else { completion(nil); return }
```

and `completion(nil)` *is* success, so a no-op was indistinguishable from a real clear.
Warden then spoke "Told Loop to clear the pod alerts" over an HTTP 200 that only meant
Nightscout had accepted the push. On 2026-11-11 that told Brian an alert had been cleared
**102 seconds before it fired** - he reported a miss, and nothing had actually been broken.

`REMOTE-ACK-HONEST-OUTCOME` fixes the reporting: success is claimed **only** on the
targeted path, where Loop's store held a real unacknowledged alert and the pod confirmed
clearing it. Otherwise it throws `noAcknowledgeableAlerts` ("No pod alerts to clear") or
`podUnreachable`, so an outcome is always recorded and silence stops being ambiguous.

Accepted trade-off, deliberately: if the pod really did still hold an alert Loop's store
had lost, this answers "no pod alerts to clear" having silently cleared it. That is the
safer of the two errors - the pod's own confirmation beep tells him the truth either way -
and the store-poisoning bug that created such orphans was itself fixed in v1.0.1.

**Still open (Brian's decision, NOT to be built unilaterally):** should "clear the pod
alerts" also cover an alert that fires in the next few minutes? It would have caught the
11/11 case, but it lets an alert sound and then clear itself seconds later, which brushes
against his own line that alerts must still FIRE. That is a therapy-safety decision.
