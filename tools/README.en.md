# tools · read-only diagnostic and verification tools

[中文](README.md) | **English**

Three browser console snippets plus one Python check that runs on your computer, all read-only.

> ⚠️ **Pasting code into the DevTools console gives that code full control over the page.** It is reasonable here only because the three console snippets below are short and neither minified nor obfuscated, so you can (and should) read them first. **Never paste console code a stranger sends you.**
> The first time you paste, Chrome blocks it and asks you to type `allow pasting` (follow the exact prompt in your browser's language).

| File | What it does | Network | Changes to the page |
|---|---|---|---|
| [`decode-check.js`](decode-check.js) (~120 lines) | Checks **hardware acceleration and decoding**: WebGL renderer (flags software renderers such as SwiftShader), AVC / HEVC / AV1 decoding at 1080p60 and 4K60, Bilibili's codec setting, then prints a verdict | **No requests at all** | Creates a canvas that is never attached to the page to read WebGL info, then releases it; result in `window.__decodeCheck` |
| [`cdn-bench.js`](cdn-bench.js) (~270 lines, ~75 of them bilingual comments) | Measures throughput and time to first byte of Bilibili's video nodes for **the current video**: cold data, single connection vs parallel, then prints a verdict | Bilibili video CDN only, no cookies, ~40 MB by default (sized from the node count) | Inserts a hidden blank iframe (to borrow the native fetch) and removes it at the end; result in `window.__cdnBench` |
| [`play-monitor.js`](play-monitor.js) (~100 lines) | Records startup time, stall count and duration, waits after seeking, forward buffer and dropped frames, for A/B comparisons | **No requests at all** | Only adds event listeners to the `<video>`; result in `window.__pm` |

| Local script | What it does | Network | Changes to the browser |
|---|---|---|---|
| [`verify-tm-install.py`](verify-tm-install.py) (Python 3.8+, standard library only) | Checks the BTR copy that Tampermonkey **actually stored**: is the code byte-identical to audited commit `0302b34`, is the header edited as in [05](../docs/en/05-safe-install.md), is "Check for updates" off; prints PASS / FAIL | **No network, no downloads** | **None**: opens Tampermonkey's storage files read-only, reads them into memory, writes no files |

**Suggested order**: `decode-check.js` first (30 seconds, rules out local playback problems) → if it still stutters, and only on unpopular videos, `cdn-bench.js` (network / CDN) → after installing BTR per 05, `verify-tm-install.py` to confirm the install → `play-monitor.js` for an A/B comparison. The full workflow is in [01 Diagnosis](../docs/en/01-diagnosis.md).

All three console snippets are written for Chromium-based browsers (Chrome / Edge); other browsers have not been tested. Every message is printed as "中文 / English". The code is released under the MIT License, see [`LICENSE`](../LICENSE).

---

## decode-check.js: rule out "this computer can't keep up"

A lot of "lag" has nothing to do with the network. When the browser's **"Use graphics acceleration when available" is off** (or the GPU is blocklisted), a 1080P60 video is decoded by the CPU, and the picture plus the danmaku overlay are composited in software too, so frames drop however fast the connection is. This snippet tells you in a few seconds.

**Usage**
1. Open any `www.bilibili.com` page (it also runs on other sites, it just cannot read Bilibili's codec setting there).
2. F12 → Console → paste the whole file → Enter.

**What it reports**

| Item | Source | How to read it |
|---|---|---|
| Browser version | `navigator.userAgentData` (falls back to the UA string) | Check `chrome://settings/help` (Edge: `edge://settings/help`) says you are up to date. If that page shows an error or never finishes, auto-update may have stopped silently; reinstalling from the official site (google.com/chrome) fixes it and keeps your profile |
| WebGL renderer | WebGL `UNMASKED_RENDERER_WEBGL` (or `RENDERER` if unavailable) | Contains `SwiftShader`, `llvmpipe`, `Basic Render` etc., or no WebGL at all → software rendering |
| Decoding table | `navigator.mediaCapabilities.decodingInfo` with type `media-source` (Bilibili's player uses MSE) | See below |
| Bilibili codec setting | `localStorage['bilibili_player_codec_prefer_type']`: `0` or unset = default, `1` HEVC, `2` AVC, `3` AV1 | Compared with the suggested codec |

One row per codec × format in the decoding table:

| Column | Meaning |
|---|---|
| 能解码 supported | Whether the browser can play this format at all. Chrome plays HEVC only with hardware decoding, so HEVC `false` often means no HEVC hardware decoder |
| 流畅 smooth | Whether the browser expects smooth playback; Chrome may take this machine's past playback statistics into account |
| 省电≈硬解 powerEfficient | In Chrome, `true` usually means a hardware decoder is used. **`false` for all three codecs at 1080p60 is the red flag** |

Query parameters: 1080p60 = 1920×1080, 60 fps, 6 Mbps, codec strings `avc1.640032` / `hev1.1.6.L123.90` / `av01.0.09M.08`; 4K60 = 3840×2160, 60 fps, 20 Mbps, `avc1.640034` / `hev1.1.6.L153.90` / `av01.0.13M.08`. Bilibili's actual streams may use slightly different codec strings, so treat the result as indicative.

**Verdicts**

| Console shows | Meaning | What to do |
|---|---|---|
| ⚠ The browser renders in software / has no WebGL | "Use graphics acceleration when available" is most likely off, or the GPU is blocklisted | Turn it on at `chrome://settings/system` (Edge: `edge://settings/system`) → click Relaunch → run this again |
| ⚠ No codec reports hardware decoding at 1080p60 | The CPU is decoding | Fix the item above first, then confirm *Video Decode: Hardware accelerated* in `chrome://gpu`. Until then, use AVC and 1080P (not 60 fps) or lower |
| Suggested codec: HEVC or AV1 | Hardware-decoded, and usually a lower bitrate than AVC at the same quality | Player ⚙ → 更多播放设置 (more settings) → 播放策略 (codec), then reload the page (the menu may change between Bilibili versions) |
| Current: default ("default" may pick AV1 …) | With "default", the player may choose AV1 whenever the browser reports it playable, and your AV1 is software-decoded | Pick the suggested codec manually |
| ✓ Hardware acceleration looks fine | Nothing wrong found in local playback | If it still stutters, test the network next with `cdn-bench.js` |

**Limits**: these are the browser's own capability claims, not measurements; `chrome://gpu` and the dropped frames recorded by `play-monitor.js` have the final word. **The output includes your GPU model**; remove it before posting screenshots publicly.

---

## cdn-bench.js: why unpopular videos buffer

**Usage**
1. For a baseline: **disable every Bilibili speed-up userscript** in your userscript manager (BTR, MBGTEB, realzza, …; they patch the page's fetch), keep VPN / WARP / proxies off, and plug in your laptop.
2. **Log in if you can.** Open `https://www.bilibili.com/video/BV…`, switch to the quality you normally watch, press **F5** (in-site navigation does not update `__playinfo__`), and **pause** as soon as the picture appears.
3. F12 → Console → paste the whole file → Enter. Wait 1–6 minutes.
4. Read the table and the final "verdict" line; `copy(JSON.stringify(__cdnBench))` copies the result so you can save it.

**What it does**: reads `window.__playinfo__` and finds the video track being played (preferring `.m4s` paths the page already requested). For the primary/backup nodes Bilibili assigned you, plus 3 overseas and 6 mainland upos nodes, it runs one single-connection Range download (2 MB) and one 8-way parallel download (2 MB in total). Every node and every test reads a **different, randomly offset** range between 25% and 90% of the file, to hit "cold" data nobody has requested recently. Non-Akamai nodes reuse a Bilibili-signed URL with the host name swapped; Akamai is tested only with its own URL (projects disagree on whether Akamai URLs work on other hosts, so they are never swapped).

**What it does not do**: no cookies (`credentials:'omit'`); every request's host is checked first, and only `*.bilivideo.com` / `*.bilivideo.cn` and the `upos-*.akamaized.net` host Bilibili assigned are allowed; no Bilibili API calls; no settings or storage changes; no uploads; the console shows host names only and **never signed URLs** (they contain your account ID and IP address).

**Settings** (`CFG` at the top of the file)

| Setting | Default | Notes |
|---|---|---|
| `OVERSEAS` / `MAINLAND` | 3 / 6 nodes | Nodes to test (`*.bilivideo.com` only) |
| `EXTRA` | empty | Extra nodes, e.g. `upos-sz-mirrorhwo1.bilivideo.com`, `upos-sz-mirror08h.bilivideo.com`. Each adds ~4 MB of traffic (the budget follows automatically when `BUDGET_MB` is 0) |
| `SINGLE_MB` | 2 | Single-connection sample. 8 reduces the underestimate caused by TCP slow start (round trips from Europe to mainland nodes are often 200–330 ms). With `BUDGET_MB` at 0 the budget grows to ~100 MB; if you set `BUDGET_MB` by hand, raise it to ≥ 110 as well |
| `PAR` / `PAR_MB` | 8 / 2 | Number of parallel requests / total parallel sample size |
| `BUDGET_MB` | 0 | Traffic cap in MB. 0 = automatic: nodes × (single + parallel sample) + 4 MB, i.e. ~40 MB for the default 10 nodes, so every node gets tested. A number = manual cap: if it is too small the console warns first and the later nodes are skipped |
| `TIMEOUT_S` | 15 | Per-request time limit; a timed-out request still counts the bytes received |
| `QN` | 0 | Force a quality id: 16=360P, 32=480P, 64=720P, 80=1080P, 112=1080P+, 116=1080P60, 120=4K; 0 = automatic |
| `TARGET_MBPS` | 0 | Bitrate (Mbps) the verdict is judged against; 0 = the current track's bitrate. **Logged out, the player often gives only 360P/480P (0.3–0.6 Mbps)**, which makes the verdict too optimistic (it nearly always says "hot"): log in and use your usual quality, or set 6 (≈1080P+) |

**Reading the table** (column names are bilingual "中文 English")

| Column | Meaning |
|---|---|
| 节点 node / 类型 role | Host name; role is 分配-主 (assigned primary), 分配-备 (assigned backup), 海外 (overseas), 大陆 (mainland) or 额外 (extra) |
| 单连 single Mbps / TTFB ms | Speed / time to first byte (including connection setup) of one connection. This is how Bilibili's own player downloads |
| 并行 parallel×N Mbps | Total speed when the same number of bytes is split into N simultaneous requests (a ceiling for multi-connection userscripts) |
| ÷码率 ÷bitrate | Speed divided by the track's bitrate (or by `TARGET_MBPS` if set; the console says so). **≥ 1.5 means there is headroom** |
| 备注 note | `超时` timeout (speed is computed from the bytes received before the timeout, so a "timeout" row can still show non-zero Mbps), `HTTP 403` refused, `HTTP 200` node ignores Range (aborted at once), `HTTP 416 超出文件末尾` past the end of the file, `Range不符` Content-Range mismatch, `多余数据` more bytes than requested, `网络错误` network error, `中止` aborted, `超出流量预算，跳过` skipped, over a manual `BUDGET_MB`. Prefixes `单连:` / `并行:` mean single / parallel. In `__cdnBench.rows[*]`, `s.note` is the single-connection note and `pNote` the parallel one |

The role and note values stay in Chinese because they are data used by the script's logic, which was deliberately left unchanged.

**Verdict and next step**

| Verdict starts with | Meaning | Next step |
|---|---|---|
| The node Bilibili assigned already gives ≥1.5× | This video is "hot" for you; the CDN is not the bottleneck | Back to [01 Diagnosis](../docs/en/01-diagnosis.md): hardware acceleration, decoding, extension conflicts |
| Another node reaches ≥1.5× … on a single connection | A different node is enough; multiple connections may not be needed | A light single-connection CDN-switch userscript (e.g. [realzza/bilibili-accelerator](https://github.com/realzza/bilibili-accelerator)) may be enough, see [04 Alternatives](../docs/en/04-alternatives.md) |
| mainland + parallel reaches 1.5× | You need mainland nodes plus multiple connections | Tools such as [BTR](https://github.com/MrTangLuyao/Bilibili-thread-ripper) (install it pinned, see [05](../docs/en/05-safe-install.md)) or the Thread Ripper module of [MBGTEB](https://github.com/SukkaW/Make-Bilibili-Great-Than-Ever-Before) are worth an A/B test |
| Only overseas + parallel reaches 1.5× | Multiple connections help; mainland nodes do not | As above (BTR's overseas mode) |
| Neither mainland nor overseas nodes reach 1.5× | The whole path is too slow | Lower the quality, use HEVC/AV1 (if hardware-decoded), or use the official app's offline cache |
| The assigned nodes are too slow, but only Akamai URLs … | No other node could be tested | Press F5 for fresh URLs, or try another video |

Why unpopular videos are so slow, and the data from each test run: [02 Why the CDN](../docs/en/02-why-cdn.md).

**FAQ**
- *"No DASH video info in window.__playinfo__"*: press F5 on the video page and retry; bangumi, paid or region-restricted pages may not have this data.
- *"The signed URLs have expired"*: the page has been open too long; press F5 and rerun.
- *Some nodes say `超出流量预算，跳过` (skipped)*: you set `BUDGET_MB` by hand and it is too small (a ⚠ line at the start says so); set it back to 0 (automatic).
- *Every node shows 0 / network error*: make sure no proxy / WARP is on and no ad-blocking extension blocks `bilivideo.com`; try another video.
- *The same unpopular video is much faster the second time*: expected, the test itself warmed the cache; pick another unpopular video you have not watched.
- *The numbers differ from a userscript's own panel*: `cdn-bench` measures what a node can deliver; a userscript panel shows what it actually scheduled. They are not the same thing.

**Limits**: one sample per node, so the result is indicative only; same-IP nodes (hw/08c/08h, …) are not independent routes, so parallel speeds of several nodes do not add up; under HTTP/2 parallel requests to one host share one connection; the single test runs first (including connection setup) and the parallel test reuses the connection, so parallel numbers are slightly optimistic; results vary with the time of day (the mainland evening peak is roughly 19:00–23:00 Beijing time, UTC+8).

---

## play-monitor.js: objective numbers for A/B tests

1. Turn off the player's autoplay (自动开播) in its settings, press F5 on the video page, and **do not press play yet**.
2. F12 → Console → paste → Enter; then press play and watch normally for 3 minutes (seek as planned).
3. It prints a line every 10 seconds; type `__pm.stop()` when done to print the summary table (also stored in `__pm.summary`).

Summary columns (kept in Chinese because they are also the keys of `__pm.summary`): 观察秒数 seconds observed · 首帧 ms startup time, from pressing play to playback starting · 卡顿次数（不含拖动）stalls, seeks excluded · 卡顿总秒 total stall time (s) · 拖动后等待次数 waits after seeking · 拖动等待总秒 total wait after seeking (s) · 当前前方缓冲 s forward buffer now (s) · 最小前方缓冲 s minimum forward buffer (s) · 丢帧/总帧 dropped / total frames · 丢帧率 % dropped frames (%).

It only reads the `<video>` element's state and events: no page changes, no requests. In the audited BTR code (commit `0302b34`), BTR keeps using the page's own `<video>` after taking over playback, so this should work with it too (not tested). Paste it again after in-site navigation to another video; Bilibili's WASM player `<bwp-video>` is not supported. The full A/B procedure and pass criteria are in [05 Safe install](../docs/en/05-safe-install.md).

---

## verify-tm-install.py: confirm you installed the audited file

After installing BTR, [05 §2 ⑤](../docs/en/05-safe-install.md) asks you to check the editor line by line. This script does those checks for you, and it looks at the code Tampermonkey **actually stored and will actually run**, not at the version number shown in the UI. Nobody can spot a one-character change in 400 KB of code by eye; SHA-256 can.

**What it checks** (each item PASS / FAIL; every FAIL comes with a fix that points to the exact step in 05)

| Check | Passes when |
|---|---|
| Version | Both the header `@version` and Tampermonkey's record say `2026.10.8.1` |
| Body | All code after `// ==/UserScript==` is byte-identical to audited commit `0302b34` (SHA-256 `793c4bc8…`, 404,509 bytes, built into the script; nothing is fetched). A difference in CRLF line endings only still passes, with a note |
| No code outside the body | The header holds only `//` comment lines and nothing precedes it (code in either place would run too) |
| `@updateURL` / `@downloadURL` | Exactly one line each, set to `none` (§2 ③A) |
| Check for updates | `options.check_for_updates` in Tampermonkey's record is `false` (§2 ③B) |
| The 4 excludes | passport / pay / account / member are all excluded, either in the header or under "User excludes"; header excludes do not count if "Original excludes" is switched off (§2 ④) |
| `@run-at` | Exactly one `@run-at document-start` line, and no line contains two `// @` directives (the glued-line problem described in §2 ④) |
| `@grant` | Exactly the 6 expected entries |
| Scope | No `@require`, `@resource`, `@connect` or `@include`; `@match` is still only `https://*.bilibili.com/*`; no extra match rules added in Tampermonkey's settings |
| Rest of the header | Apart from the allowed edits above, identical line by line to the audited header (`@sandbox`, `@inject-into`, `@namespace`, …) |

Also reported, without affecting the verdict: whether the script is enabled; the update URLs in Tampermonkey's record; whether it was installed from the pinned commit URL; when it was last modified; duplicate installs; Tampermonkey BETA.

**Usage** (Python 3.8 or newer; on Windows get it from python.org and use `py` or `python` instead of `python3`)

```
python3 verify-tm-install.py                 # scan every profile of Chrome / Edge / Brave / Chromium / Opera
python3 verify-tm-install.py --browser chrome --profile "Default"
python3 verify-tm-install.py --profile-dir "<profile path>"
python3 verify-tm-install.py --audited-file bilibili-thread-ripper.user.js   # optional, see below
python3 verify-tm-install.py --lang en        # English only (zh = Chinese only; default: both)
python3 verify-tm-install.py --self-test      # test the built-in LevelDB / Snappy readers
```

- The profile path is the "Profile Path" line on `chrome://version` (Edge: `edge://version`).
- `--audited-file`: the pinned file saved as suggested in [05 §2 ①](../docs/en/05-safe-install.md). The script checks its SHA-256 first, then uses it to show the line of the first difference if the body does not match.
- By default it looks for Tampermonkey's 6 official extension IDs ([FAQ Q406](https://www.tampermonkey.net/faq.php?locale=en&q=Q406#Q406): stable, BETA and Legacy from the Chrome / Edge / Opera stores); add others with `--ext-id`. A renamed copy is still found through its `@namespace`; `--name` matches a different name.
- It works while the browser is open. Exit code: 0 = PASS, 1 = FAIL, 2 = not found or error, so you can put it in your own periodic check.

Sample output (trimmed; this is exactly what "③A done, ③B not done" looks like):

```
== Chrome · Default · Tampermonkey (Chrome Web Store) ==
  [PASS] Body (the code that runs) is byte-identical to audited commit 0302b34
  [PASS] @updateURL none
  [PASS] @downloadURL none
  [FAIL] "Check for updates" is still ticked (options.check_for_updates = true)
         → Fix: script "Settings" tab → untick "Check for updates" → save (05 §2 ③B)
  [PASS] The 4 sensitive-subdomain excludes are all present
  [PASS] @run-at document-start is on its own line; no glued lines
  ...
  Verdict: FAIL, 1 check(s) failed (see the → Fix lines above).
```

**What it reads, and how**

Tampermonkey keeps scripts in `chrome.storage.local`, i.e. the `Local Extension Settings/<extension ID>` folder of the browser profile, which is a LevelDB database. The script reads **only that folder**, and it parses the LevelDB format layer by layer instead of searching the files for text:

- **`.log` (write-ahead log)**: 32 KiB blocks, each record with a 7-byte header (CRC32C, length, type). FULL / FIRST / MIDDLE / LAST fragments are joined back into whole records, the CRC is verified, and the WriteBatch inside (sequence number, count, then each key and value) is decoded. A 400 KB script spans a dozen blocks, so a plain text search gets cut by block headers and stitches together the wrong content;
- **`.ldb` (tables)**: footer, index block and data blocks, with a built-in pure-Python Snappy decompressor and a CRC32C check on every block;
- **`MANIFEST`**: decides which `.log` / `.ldb` files are still live, so obsolete files are ignored;
- for each key the record with the highest sequence number wins (deletions included), so you see Tampermonkey's current state, not an old version.

Keys used: `@source#…` (the full script text) and `@meta#…` (Tampermonkey's parsed metadata and this script's settings).

**Privacy and safety**

- **Read-only**: every file is opened for reading only (on Windows, sharing read, write and delete, so the browser is never blocked), read into memory and closed straight away. **No files are written** (temporary files included), nothing goes over the network, nothing is downloaded, the browser is not called.
- **Only the matched script is printed.** Names, code, settings and stored data of your other scripts are never printed; you only see a count of installed scripts.
- No script IDs and no local paths are printed. Update URLs are shown as `none`, the pinned commit URL or the main URL; any other https URL is reduced to its host, and local file URLs are not shown. The output is safe to paste into an issue.
- Cookies are not stored in that folder, and the script does not read them.
- About 1,100 lines, neither minified nor obfuscated, standard library only; roughly half of it is the LevelDB / Snappy readers and the self-test.

**Limits**

- Tampermonkey in Chromium-based browsers only. Violentmonkey, Firefox and Safari are not supported; for Violentmonkey, check by hand per [05 §3](../docs/en/05-safe-install.md) step 4.
- It checks the stored record only. Whether BTR is really active on the page and whether the passport page is really excluded still needs the quick in-browser look in 05 §2 ⑤.
- It does not read Tampermonkey's global settings, so the optional §2 ③C (global update interval) is not checked.
- Table blocks are supported uncompressed or Snappy-compressed only. Other formats are reported and skipped; if that happens, change something on BTR in Tampermonkey (e.g. disable and re-enable it) so the latest record is written to the `.log`, then re-run.
- It relies on Tampermonkey's current storage format (keys `@source#` / `@meta#`, the setting `options.check_for_updates`), confirmed with Tampermonkey 5.5.1 on 2026-10-13. A future version that changes the format may make it report "not found" or "could not read the setting".
- It only knows audited commit `0302b34` (v2026.10.8.1). After upgrading to a newer commit per [05 §4](../docs/en/05-safe-install.md), the body and version checks will FAIL. That is expected: a new version has to be reviewed first.
- A matching body only means the code is the same as when it was audited. What the audit did and did not cover is in [03](../docs/en/03-btr-security-audit.md).

---

## Test status (stated plainly)

**cdn-bench.js**
- **Mock environment**: a fake `__playinfo__` and fake CDN responses (no real network requests) covering mixed faults (timeout / 403 / 200 / Range mismatch / excess data / network error), slow cold nodes, Akamai-only URLs, missing `__playinfo__`, stale `__playinfo__` plus unknown file size, illegal hosts (ignored), automatic and manual traffic budgets, and every verdict branch except "bitrate unknown". (A forced quality via `QN` and the "bitrate unknown" case are not covered by the mock tests.) Checked: every request uses `credentials:'omit'`, only allowed hosts are contacted, byte ranges never overlap and stay mid-file, total traffic matches the plan printed at the start, the iframe is removed, no signed URLs in the result.
- **Real Bilibili page, logged out** (2026-10-13, a pre-v1.1 build, Chromium-based browser): unpopular video BV1EqYE6iEu5 (64 views, ~3 hours) ran to completion: all 10 nodes tested, ~40 MB, table and verdict printed, iframe removed, no signed URLs in the result. That run exposed a problem: logged out the player only offered 360P (0.40 Mbps), so the verdict wrongly said "hot", which is why v1.1 added `TARGET_MBPS` and the low-bitrate warning.
- **Real Bilibili page, logged in** (2026-10-13, Chrome, same benchmark logic): unpopular video BV1wqbT6AEbe (65 views, ~4 hours, 1080P60 AVC, declared bitrate 3.48 Mbps), all 10 nodes tested. Data and interpretation in [02](../docs/en/02-why-cdn.md).
- **This bilingual edition**: only comments, console message text and table column names changed; **the measuring logic is the same as v1.1**. Two checks: (1) a small tokenizer script compared the two versions: after stripping comments both have the same number of tokens, and apart from string text the only difference is the 3 table column names (`节点`, `类型`, `备注` changed from bare identifiers to quoted bilingual strings, display only); (2) the 13 mock scenarios above were run against both versions in the same harness: request count, hosts contacted, byte ranges, total traffic, iframe removal, result object, table rows and verdict branch were identical. The bilingual edition itself has not been re-run on a real Bilibili page.

**play-monitor.js**
- **Mock environment** (earlier).
- **Local test page** (2026-10-13, Chromium-based browser): a WebM video generated in the browser plus synthetic `waiting` / `playing` events: stall count and duration, waits after seeking, the 10-second log line, the `__pm.stop()` summary and the "no `<video>`" warning all behaved as expected.
- **Real Bilibili page** (2026-10-13, logged out, Chromium-based browser with hardware acceleration on, pasted code identical to this file): popular video BV15KpR6TENe played for ~30 seconds with one seek: startup time, the 10-second lines, the wait after seeking, forward buffer, dropped frames and the summary table were all reported.
- **Not tested yet**: a real stall on an unpopular video; playback taken over by BTR.

**decode-check.js** (new in this release)
- **Mock environment**: faked WebGL and `mediaCapabilities` answers covering 10 cases: SwiftShader with no hardware decoding for any codec (the case-study situation), full hardware decoding, HEVC-only hardware decoding with the codec setting on default, AVC selected while HEVC is hardware-decoded, no WebGL, no `mediaCapabilities`, a non-Bilibili site, a rejected query plus no `userAgentData`, AVC-only hardware decoding, and an unknown codec-setting value. Every case produced the expected verdict without errors, and the canvas was released.
- **Real Bilibili page** (2026-10-13, logged out, same browser as above, pasted code identical to this file): results appeared immediately; all six queries reported supported / smooth / powerEfficient = true, the verdict was "✓ Hardware acceleration looks fine" with HEVC or AV1 suggested, and no canvas was left on the page.
- **Not tested yet**: a browser with hardware acceleration actually turned off. The "software rendering / no hardware decoding" verdict has so far been verified in the mock environment only.

**verify-tm-install.py** (new in this release)
- **Self-test** (`--self-test`): the standard CRC32C check value, Snappy decompression (including overlapping copies and two kinds of corrupt input), FIRST / MIDDLE / LAST fragments across blocks, WriteBatch decoding, and dropping of damaged fragments.
- **Simulated cases**: 16 header / settings combinations, all with the expected verdict. Passing: edited as in the guide, CRLF line endings, excludes under "User excludes", a BOM at the start of the file. Failing: "Check for updates" still ticked, setting unreadable, "Original excludes" switched off, an added `@require`, code before the header, a non-comment line inside the header, one changed character in the body, an added `@grant GM_cookie`, extra match rules in the settings, the unedited release file, a changed `@name`. Warning only: script disabled plus an overridden run-at time. One end-to-end run on a synthetic LevelDB log: a renamed copy was found through its `@namespace`, `--audited-file` reported the correct line of the first difference, and another script in the same storage did not appear in the output.
- **Corrupt input**: random byte overwrites and random truncation of copies of a real storage (`.log`, `.ldb`, `MANIFEST`), 60 rounds each, plus 300 random Snappy inputs: no crashes; damaged parts were skipped and counted.
- **Real storage** (2026-10-13, Windows, Chrome, Tampermonkey 5.5.1, browser open):
  - Current storage: 1 `.log` and 1 `.ldb` read in under a second. Body byte-identical; `@updateURL` / `@downloadURL` set to `none`; the 4 excludes, `@run-at`, the 6 `@grant`, scope and the rest of the header all passed; the only FAIL was "Check for updates" still being ticked. That matches the observation recorded in [05 §2 ③B](../docs/en/05-safe-install.md): editing the header alone does not switch that setting off.
  - A copy of the same storage taken earlier that day (right after the header edit): the tool flagged the glued line described in §2 ④, `// @exclude      https://member.bilibili.com/*// @run-at       document-start`, and reported the member exclude and `@run-at` as missing because of it.
  - Tables: all 313 data blocks passed the CRC check and decompressed, and the keys came out in LevelDB's sort order.
  - A profile with Tampermonkey installed but no scripts: reported "BTR was not found", exit code 2.
  - Run on Python 3.11, 3.12 and 3.13; syntax checked against the 3.8 grammar.
- **Not tested yet**: macOS and Linux; Edge, Brave, Opera or Chromium with BTR actually installed; Tampermonkey BETA; actually running on Python 3.8–3.10.

If something fails in your browser, please open an issue with a console screenshot (remove your GPU model or anything else you do not want public first).
