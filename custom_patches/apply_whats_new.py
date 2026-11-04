#!/usr/bin/env python3
"""Personal version number + once-per-version What's New sheet.

Run from the LoopWorkspace root, during the Customize Loop step, AFTER the Loop and
Learn CustomizationSelect.sh customizations.

WHY THIS IS NOT A .patch FILE
-----------------------------
It was one, and it failed four builds in a row with "patch does not apply" at
SettingsView.swift:50 -- while the byte-identical patch applied to the byte-identical
pinned blob locally. The cause: `basal_lock`, one of the Loop and Learn customizations
run earlier in the same step, adds a Preferences feature that inserts

    case preferences

directly after `case favoriteFoods` -- exactly where the patch anchored -- plus 15 more
lines elsewhere in the file. A context diff generated against the pristine blob can
therefore never apply.

Worse, CustomizationSelect.sh is fetched live from loopandlearn/lnl-scripts@main and is
not pinned, so its output can change again at any time. Anchored single-string edits
survive that; three lines of surrounding context do not.

Every edit asserts its anchor is present EXACTLY once and exits non-zero otherwise, so
upstream drift fails the build loudly instead of silently dropping the feature. The
Verify Customizations step is the second net.
"""
import io
import sys

SETTINGS = "Loop/Loop/Views/SettingsView.swift"
STATUS = "Loop/Loop/View Controllers/StatusTableViewController.swift"


def edit(path, old, new, what):
    s = io.open(path, encoding="utf-8").read()
    n = s.count(old)
    if n != 1:
        sys.exit("What's New: %s -- anchor found %d times (expected 1) in %s:\n  %r"
                 % (what, n, path, old[:90]))
    io.open(path, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("  ok: %s" % what)


def append(path, text, marker, what):
    s = io.open(path, encoding="utf-8").read()
    if marker in s:
        sys.exit("What's New: %s -- %s already contains %r" % (what, path, marker))
    io.open(path, "w", encoding="utf-8").write(s.rstrip("\n") + "\n" + text)
    print("  ok: %s" % what)


# --------------------------------------------------------------- SettingsView.swift

# 1. a Sheet case. Anchored on the case itself, NOT on what follows it, because
#    basal_lock inserts `case preferences` on the next line.
edit(SETTINGS,
     "            case favoriteFoods\n",
     "            case favoriteFoods\n"
     "            case whatsNew\n",
     "Sheet enum case")

# 2. the sheet switch arm, inserted BEFORE the favoriteFoods arm for the same reason.
edit(SETTINGS,
     "                case .favoriteFoods:\n",
     "                case .whatsNew:\n"
     "                    WhatsNewView(onDone: { self.sheet = nil })\n"
     "                case .favoriteFoods:\n",
     "sheet switch arm")

# 3. a row in the Loop section, whose header already carries the upstream app version.
edit(SETTINGS,
     "            .disabled(!viewModel.isOnboardingComplete || !viewModel.isClosedLoopAllowed)\n",
     "            .disabled(!viewModel.isOnboardingComplete || !viewModel.isClosedLoopAllowed)\n"
     "\n"
     "            // Keeps What's New reachable after the one-time sheet is dismissed.\n"
     "            Button(action: { self.sheet = .whatsNew }) {\n"
     "                HStack {\n"
     "                    Text(NSLocalizedString(\"What's New\", comment: \"Settings row that re-opens the What's New screen\"))\n"
     "                        .foregroundColor(.primary)\n"
     "                    Spacer()\n"
     "                    Text(BrianBuild.version)\n"
     "                        .foregroundColor(.secondary)\n"
     "                }\n"
     "            }\n",
     "Settings row")

WHATS_NEW = '''
// MARK: - Personal version and What's New (Brian, 2026-11-01)

/// Standing rule: every release ships a real user-visible version plus a once-per-version
/// What's New. This app is a FORK, so `CFBundleShortVersionString` deliberately stays equal
/// to the UPSTREAM Loop release it is built from -- that number is what the Loop community,
/// Loop's diagnostics and Nightscout all read, and inventing a value there would misreport
/// which Loop is running on a medical device.
///
/// It would also break things. Nightscout's `loop.version` is literally
/// "<marketing>.<build>" (NightscoutServiceKit Bundle.fullVersionString), and Warden's
/// pod-alert gate compares it with PHP `version_compare`. Measured, not assumed:
/// "3.14.11-tlp.1.25" compares LESS THAN "3.14.11.24", because an unknown alphabetic
/// segment sorts below a plain number -- so a "-tlp.N" marketing version would jam that
/// gate shut forever.
///
/// The personal version therefore lives here, and is what the What's New is keyed to.
enum BrianBuild {

    /// BUMP THIS ON EVERY RELEASE. MAJOR.MINOR.PATCH -- minor for features, patch for fixes.
    static let version = "1.0.1"

    /// One short plain-English line per item. No jargon; engineering detail belongs in the
    /// commit message, not here.
    static let whatsNew: [String] = [
        NSLocalizedString("Clearing a pod alert by voice now actually reaches the pod, and keeps trying if the pod is out of range.", comment: "What's New item"),
        NSLocalizedString("If it cannot reach the pod it says so, instead of claiming there was nothing to clear.", comment: "What's New item"),
        NSLocalizedString("Only reminders can be cleared this way. A real pod fault always stays on screen.", comment: "What's New item")
    ]

    private static let lastSeenKey = "com.thelostping.loop.lastSeenWhatsNewVersion"

    /// True once per version: the first time the app is opened after an update.
    static var shouldShowWhatsNew: Bool {
        UserDefaults.standard.string(forKey: lastSeenKey) != version
    }

    static func markWhatsNewSeen() {
        UserDefaults.standard.set(version, forKey: lastSeenKey)
    }

    /// e.g. "Based on Loop 3.14.11 (26)"
    static var basedOnDescription: String {
        let short = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return String(format: NSLocalizedString("Based on Loop %1$@ (%2$@)", comment: "What's New subtitle: the upstream Loop release this build was made from (1: upstream version, 2: build number)"), short, build)
    }
}

struct WhatsNewView: View {

    let onDone: () -> Void

    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        Text(BrianBuild.basedOnDescription)
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        ForEach(BrianBuild.whatsNew, id: \\.self) { item in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: "circle.fill")
                                    .font(.system(size: 6))
                                    .foregroundColor(.accentColor)
                                    .padding(.top, 7)
                                Text(item)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top)
                }

                Button(action: onDone) {
                    Text(NSLocalizedString("Got it", comment: "Button that dismisses the What's New screen"))
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding()
                }
                .buttonStyle(.borderedProminent)
                .padding()
            }
            .navigationTitle(String(format: NSLocalizedString("What's New in %1$@", comment: "What's New screen title (1: personal version number)"), BrianBuild.version))
            .navigationBarTitleDisplayMode(.inline)
        }
        .navigationViewStyle(.stack)
    }
}
'''

append(SETTINGS, WHATS_NEW, "enum BrianBuild", "BrianBuild + WhatsNewView")

# ----------------------------------------------------- StatusTableViewController.swift
# Nothing else in this build touches this file, but anchor it the same way anyway.
edit(STATUS,
     "        onscreen = true\n",
     "        presentWhatsNewIfNeeded()\n"
     "\n"
     "        onscreen = true\n",
     "viewDidAppear hook")

STATUS_EXT = '''
// MARK: - What's New (Brian, 2026-11-01)

extension StatusTableViewController {

    /// Shows the What's New sheet once per personal version, on the first launch after an update.
    ///
    /// SAFE TO PRESENT HERE: LoopAppManager, which is the AlertPresenter, presents alerts on
    /// `rootViewController.topmostViewController`, so a pod or device alert still appears OVER
    /// this sheet rather than being swallowed by it. Verified in
    /// LoopAppManager.present(_:animated:completion:).
    ///
    /// The seen-marker is written BEFORE presenting, so a crash or force-quit while it is on
    /// screen cannot turn this into a sheet that reappears at every launch.
    func presentWhatsNewIfNeeded() {
        guard BrianBuild.shouldShowWhatsNew else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self = self, self.presentedViewController == nil else { return }

            BrianBuild.markWhatsNewSeen()

            let hostingController = UIHostingController(
                rootView: WhatsNewView(onDone: { [weak self] in
                    // Dismissing from the PRESENTER dismisses what it presented, which avoids
                    // the retain cycle a self-reference inside the view would create.
                    self?.dismiss(animated: true)
                })
            )
            self.present(hostingController, animated: true)
        }
    }
}
'''

# marker is the DEFINITION, not the call we just inserted into viewDidAppear
append(STATUS, STATUS_EXT, "func presentWhatsNewIfNeeded()", "StatusTableViewController extension")

print("What's New: all edits applied (version %s)" % "1.0.1")
