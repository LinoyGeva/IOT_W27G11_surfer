# Atlas BLE investigation: from recorded batches to live notifications

This document explains the sequence of questions, experiments and discoveries.
The [current specification](README.md) owns UUIDs, activation, packet layout,
run commands and runtime policy. Findings below are tied to their evidence;
failed trials remain visible rather than being rewritten as successes.

The work took place on 2026-11-09 and 2026-11-10. Earlier records and phone/Mac
captures have different clock contexts; dates identify artifacts, not a
calibrated cross-device timeline. Most scripts were uncommitted during testing.
Capture metadata records the Git HEAD, but that hash alone does not identify
those working files. Keep the raw artifacts and the archived source snapshot
when reproducing an experiment.

## Starting question

The goal was current board attitude on an offline receiver, eventually the
Raspberry Pi running Android. The acceptance question was whether received Heel
and Trim follow controlled tilts and agree with the physical Atlas screen.
Receiving any BLE bytes, producing a graph or downloading a valid recording
would not by itself answer that question.

Early work had no verified live activation command, packet contract or known
relation between raw orientation and the display's mounting corrections,
zero offsets and damping. Python on the Mac was chosen for investigation,
without changing the Android-on-Pi deployment decision.

## 1. The HTTP API was an alternative route, not a local BLE solution

We reviewed the supplied telemetry API schema and public historical data. The
schema provided event-based telemetry queries and an offline batch-upload
operation. It did not establish how our standalone device would be registered,
upload current data or create a solo training event. Device identity, event
provisioning, uploader access, units and freshness still needed confirmation.

This route could not establish direct offline acquisition. It was kept as
research context while local BLE became the focus. The historical HTTP data
was never evidence of a working live signal from our Atlas.

Reference material: the supplied `Downloads/document.yaml`, the reviewed
[telemetry schema](https://teleapi.regatta.app/openapi.yaml), and Vakaros's
[RaceSense live-tracking description](https://www.vakaros.com/blogs/news/racesense-live-tracking-bringing-every-race-to-the-world-in-real-time).
These sources were reviewed during the investigation; this document does not
claim that the service's current behavior was retested during cleanup.

## 2. Discovery and subscriptions worked, but passive acquisition was silent

The first diagnostics scanned advertisements, connected and inventoried GATT
services, characteristics and notification capabilities. They deliberately did
not guess application commands. A saved capture named
`live-capture-20261109T094314272009Z.jsonl` showed two successful subscriptions,
no disconnect and zero packets over a 60-second observation.

That ruled out neither live telemetry nor a required activation exchange. It
established only that connecting and subscribing alone had not started a stream
in that trial. Later device-information reads identified model `Atlas2,0` and
firmware `0.32.0`; firmware details were not recorded in every early capture.

## 3. A known recorded-log protocol proved request/reply connectivity

We inspected [koheik/atlas-ble-client](https://github.com/koheik/atlas-ble-client/blob/66daf1e453edd12c17f3e42d41be26bae86e4301/src/atlas_ble_client/client.py)
at revision `66daf1e453edd12c17f3e42d41be26bae86e4301`. Its session-list request
and chunk-download path matched the observed characteristic UUIDs. We tested
those fixed commands rather than interpreting arbitrary notifying bytes as angles.

Session replies showed a growing recording: the newest reported chunk increased
from 3231 to 3236 between two user runs. A later connectivity audit,
`diagnosis-20261109T144659114407Z.json`, tested two fresh connections. It obtained
eight complete session replies in roughly 59–122 ms, successfully resubscribed,
retrieved a known recording with a valid CRC and received a consistent empty
reply for an unavailable chunk. Both passive observation windows were silent.

This established a working log request/reply path without an additional
application authentication exchange in those tests. It did not establish the
live activation sequence, or prove that authentication is absent from every
other operation or firmware version.

## 4. Recorded orientation decoded correctly, but arrived in batches

A physical download of chunk 3235 yielded 2,032 CRC-verified bytes and 45
position/velocity/orientation records spanning 25 seconds of device log time.
The payload matched the vendor's [VKX 1.4 record layout](https://github.com/vakaros/vkx).
We retained transport framing separately from decoded record semantics.

An analyzer exposed record timestamps, position, speed/course, altitude and
quaternions. Candidate roll/pitch/yaw were calculated under an explicit
normalized-quaternion ZYX assumption. At this stage, those calculated angles
were not verified against the display.

The first graph repeatedly fetched the newest recorded chunk, checked its CRC,
decoded it and plotted new timestamped samples. This was useful for inspecting
recordings but created the observed bursts. In
`follow-20261110T085427433667Z.jsonl`, most chunks contributed 44–45 samples
covering about 21.5–22 seconds. The Python journal flushed each event; console
buffering did not explain those batches. The receiver also waited for a full
CRC-validated chunk before publishing its rows.

**Decision:** do not solve a recording delay with animation or by relabeling
replay as live. Faster polling could detect available chunks sooner, but could
not force the Atlas to expose current samples through that recording interface.

## 5. Empty plots needed a recording-state diagnosis

Some session replies contained an untimestamped entry with zero start/end times
and an unavailable newest chunk. The graph excluded closed recordings and could
therefore wait even though the BLE connection and old recordings were readable.
The exact empty transfer reply was recognized without treating it as a new sample.

`diagnosis-20261109T143556239083Z.json` recorded a closed chunk with 14 valid
orientation records while no timestamped ongoing recording was available.
An unsubscribe error was preserved separately rather than hiding the completed
reads. Other captures showed a recording ending and sample age increasing.

This explained particular blank or frozen recorded views. It did not identify
whether logging settings, GNSS/time initialization or another device state
caused an absent ongoing recording. Indoor/outdoor and logging-setting hypotheses
remained unresolved and were not promoted into activation instructions.

## 6. The external live repository was useful research, not working proof

The user requested an independent test of
[JPsnipe/vakaroslive](https://github.com/JPsnipe/vakaroslive/tree/0fc8b6ea5f7e5d05fe588ef56eb9035c95e52586)
at revision `0fc8b6ea5f7e5d05fe588ef56eb9035c95e52586`. It was cloned outside
AeroVision into `/private/tmp/vakaroslive-atlas-20261109` and given an isolated
Python 3.12.14 environment. Requirements installed using prebuilt PyObjC wheels;
this avoided repeating the earlier Python 3.9 compilation failure.

The bridge discovered and connected to the Atlas but initially received no usable
telemetry. Its fallback characteristic reads failed with ATT error 2, Read Not
Permitted. An independent local diagnostic reproduced those rejected reads on
all four proprietary characteristics.

The companion BLE client sent a single-byte `01` wake-up candidate and retried
it after five seconds. Acknowledged writes did not establish streaming on our
firmware. Further authorized trials tested a second command channel, an `02`
alternative, a write without response, activation before subscription and an
explicit `02 0a` query hypothesis. The tested windows produced no candidate live
notifications while known log requests still worked.

Evidence includes:

- `diagnosis-20261109T145422037744Z.json`: rejected telemetry reads.
- `diagnosis-20261109T145538537097Z.json`: acknowledged single-byte candidate,
  no notifications in the following ten seconds.
- `diagnosis-20261109T150255891077Z.json`: five isolated variants, no candidate
  notifications in their twelve-second windows.
- `diagnosis-20261109T150341849033Z.json`: query inferred from a reply header,
  also unsuccessful.
- The separate clone's `EXPERIMENT.md`, `bridge-wakeup.log`, `motion-poll.jsonl`
  and companion-manager probe: a connected but silent result, including a
  60-sample API poll with both angles null.

No reboot, reset, firmware modification or arbitrary opcode sweep was used.
The failed candidate was not the same application command eventually observed
from the working phone.

## 7. A real state-update bug explained one kind of null value

The user reproduced an external-repository bug using a synthetic packet: valid
angle fields were discarded when coordinates were near zero. The external
`state.py` returned before processing independent attitude fields.

We reproduced and fixed that guard in the separate clone. Regression checks
showed that invalid GPS could be excluded from position calculations while
changing angle fields continued to update. Those software checks did not create
physical telemetry, and were not evidence that the single-byte candidate worked.

Some later captures contained short `02 0b` replies. The external decoder's broad
acceptance of any `02` header risked interpreting such replies as telemetry.
Our investigation already knew that subtype from session-list queries. The new
receiver therefore classifies header and channel before extracting floats;
long session replies cannot masquerade as angles.

## 8. Capturing the working phone exposed the missing exchange

The user then confirmed that Connect on the iPhone displayed angles immediately,
matching the physical Atlas screen. That supplied the working reference the
Mac experiments had lacked. The iPhone was connected to the Mac by USB and its
Bluetooth exchange was saved with PacketLogger. Those Apple tools were used
only for protocol discovery, not as a dependency of the final receiver.

The trace is [vakaros_ble1.pklg](../../packet_inspection/vakaros_ble1.pklg),
SHA-256 `0b65371bef42e04227ae7078bc36eaee32847f246defe19eb26cb15356caf0bd`.
Offline extraction validated ACL/L2CAP lengths and fragment completion. It
found 5,781 PacketLogger records, 840 fixed-channel ATT packets and 520
35-byte main-channel live notifications. The extracted files and offline
inspection script are in `local_data/vakaros_atlas/pklg-20261110/`.

The decisive ordering was: notification subscriptions completed; Connect sent a
configuration-like query; then a session-list query and the activation bytes
identified in the specification. The first live packet followed that activation
by about 355 ms. Notifications continued for 133.592 seconds, with receive gaps
of 117–420 ms and a median of 270 ms. They continued after the separate recorded
chunk downloads had finished. No live stop command was identified.

This distinguished a real notification stream from the earlier recorded batches.
The trace's configuration records also mapped its ATT handles to characteristic
UUIDs, allowing us to use ordinary GATT operations instead of copying iPhone-local
handles. The candidate activation could now be tested independently.

## 9. The app export checked recorded angle interpretation

The user supplied [A10 11-10-2026.csv](<../../packet_inspection/A10 11-10-2026.csv>),
with explicit Heel/Trim and quaternion columns. All 727 exported rows matched
timestamped quaternion records reconstructed from 26 CRC-verified chunk downloads
inside the phone trace. Quaternion components agreed within the export's
nine-decimal rounding, with maximum absolute difference below `5e-10`.

Our recorded quaternion-to-Euler conversion agreed with exported Heel/Trim to
within 0.052 degrees over this file. Its pose range was narrow: Heel -3.3 to
-1.1 and Trim 80.1 to 80.9 degrees. This validates the comparison for those
recorded samples, not all mounting modes or the complete motion range.

The last exported angles were Heel -1.9 and Trim 80.6. The first live packet's
presumed fields became -1.9687 and 80.5932 under signed wrapping. That supported
the mapping and wrapping interpretation. It was not a synchronized live match:
the exported timestamp normalized to `10:22:49.500Z`, while the first live packet
was received at `12:22:49.285Z`. We did not silently shift the data to hide this
roughly two-hour source-clock discrepancy. Its cause remains unexplained.

The comparison summary and reconstructed samples are in the same ignored
`pklg-20261110/` directory. The original CSV and trace were not changed.

## Direct Mac reception

With the captured activation exchange, the user ran the notification-only
receiver. Its saved log,
[notification-live-20261110T113129067260Z.jsonl](../../local_data/vakaros_atlas/notification-live-20261110T113129067260Z.jsonl),
contains the observed command once, without a GATT response, after two subscriptions.
It contains no log-list or chunk-download requests.

The Mac received 239 live-format packets over 59.700 seconds. The first arrived
about 150 ms after the request attempt. Receive gaps measured with the Mac's
monotonic clock were 90–390 ms, median 240 ms and arithmetic mean about 250.8 ms.
No gap exceeded one second. This established independent direct Mac reception
at roughly four packets per second in that run.

Angle candidates changed substantially: under signed wrapping, Heel ranged from
-89.92 to +85.96 and Trim from -29.94 to +66.74 degrees. Final candidates were
Heel -2.5243 and Trim +1.8839. These changes were consistent with the requested
tilts, but we did not receive simultaneous screen measurements for the run.
Phone closure was requested rather than independently detected by the software.
Power-cycle independence and Android/Pi behavior were not established.

## 10. The graph was changed to consume the live receiver

The initial graph still used recorded-chunk polling, which explained why it
continued to jump even after notification-only acquisition succeeded. We changed
it to publish incoming live candidates directly into the display queue, use
signed angles and plot Mac reception time. A separate collector kept BLE handling
independent of rendering. The graph added reception freshness and a per-connection
mean packet gap rather than pretending its receive time was device sample time.

Headless renders using saved packets were explicitly labeled offline visual
checks. They checked layout and rendering, not a new physical session. The
recorded viewer remained selectable briefly, then was removed from the active
folder in the cleanup described below.

## 11. Reconnection revealed a separate silent-link failure

The first reconnect loop created fresh clients within the same collector process.
Synthetic tests passed, but the user's physical test showed a missing case.
`notification-live-20261110T114623396225Z.jsonl` received 706 candidates on its
first connection. A second connection subscribed and sent activation but received
zero angle packets for about 161 seconds before another disconnect. Later scans
did not find the device. BLE connection state alone had not guaranteed a stream.

The user reported that Ctrl+C and restarting the command connected successfully.
A subsequent capture, `notification-live-20261110T115514742727Z.jsonl`, showed
packets arriving again. This did not identify an OS or firmware root cause, but
it justified matching the successful manual recovery rather than waiting forever
on a silent connected session.

The current graph supervises a new collector process on each attempt and treats
prolonged angle silence as a failure. It can terminate hung cleanup, excludes
old-process output and keeps the window open. Exact thresholds belong in the
[specification](README.md#graph-lifecycle-and-reconnect-policy). Software and
real synthetic-output subprocess checks pass. A repeatable physical test of this
latest recovery policy is still pending; passing software tests does not close it.

## 12. Cleanup: retain the live path and preserve the investigation

The active folder now contains the receiver, graph, their tests, dependency files
and exactly two Markdown documents. Discovery, journaling and environment helpers
were moved into the live receiver so it no longer depends on the old probes.
The old chunk analyzer/downloader, speculative diagnostic scripts, their tests,
recorded-mode graph branches, single-byte trigger option and unused in-process
retry helper were removed from the active implementation.

Before removal, the entire old Atlas folder was copied to ignored
`local_data/vakaros_atlas/archive-before-cleanup-20261110T133919Z/`, including its
original large README. `snapshot-manifest.json` records file hashes. This snapshot
is archival source context, not the maintained runnable interface. All original
JSONL/BIN/CSV/PacketLogger evidence remains outside Git. The separate external
clone was left outside AeroVision and was not converted into project code.

The cleanup's retained test suite covers current behavior only; tests for removed
experimental paths were removed with them. The final cleanup verification is
recorded in the task result rather than reusing historical test counts as a
hardware claim.

## What is established and what remains

The investigation progressed from passive silence, through a working but buffered
recorded-data path, to a captured activation exchange and direct Mac notifications.
It established the live transport mechanism needed for further integration. It
has not established a universal Atlas SDK, all field semantics or acceptance on
the final hardware. The [specification's integration checklist](README.md#porting-the-protocol-to-the-android-pi)
defines the remaining screen, timing, recovery and Android/Pi checks.

Raw artifacts are intentionally local and ignored, so links to them may be absent
in a fresh clone. Maintained facts stay in these two documents; the archival
artifacts explain how those facts were obtained.
