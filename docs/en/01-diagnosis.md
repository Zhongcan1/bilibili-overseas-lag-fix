# 01 · Diagnosis: buffering or decoding?

[简体中文](../zh-CN/01-diagnosis.md) · **English** · [← Back to README](../../README.en.md)

> **In one line**: rule out your local playback stack, especially hardware acceleration, before you blame the network. Checking it is free and risk-free, and in our Netherlands case study it was exactly the half of the problem everyone overlooked.

## 1. Two kinds of stutter, and how they look different

| What you see | More likely | Where to go |
|---|---|---|
| Spinner; sound and picture stop together; the grey buffer bar catches up with the playhead; **only unpopular videos** do this | **Buffering** (network / CDN) | [02 · Causes and benchmarks](02-why-cdn.md) |
| No spinner; sound keeps going while the picture judders; the buffer bar is far ahead; the dropped-frame count keeps rising; **popular videos do it too** | **Decoding / rendering** (local) | §2–§5 below |
| No dropped frames and plenty of buffer, but motion looks uneven | Refresh-rate cadence mismatch (e.g. 60 fps video on a 144 Hz screen), or G-SYNC in windowed mode | §5 |
| It goes away when danmaku (bullet comments) are turned off | Danmaku rendering load is too heavy | §5 |
| It goes away in a Guest window (no extensions) | An extension or userscript | §5 |

The two causes **can happen at the same time**. That is what the Netherlands case study showed: hardware acceleration was off, and the CDN was slow for unpopular videos.

## 2. Step one: is hardware acceleration on?

### Why it matters so much

When the browser's "Use graphics acceleration when available" setting is off:

- **Video decoding** is done entirely by the CPU;
- **Page compositing and WebGL** are handled by [SwiftShader](https://github.com/google/swiftshader), Chrome's built-in CPU software renderer;
- In Chrome, **HEVC is hardware-decode only** (the Chromium source [`media/media_options.gni`](https://github.com/chromium/chromium/blob/main/media/media_options.gni) states that HEVC decoding must be provided by the platform), so with hardware acceleration off HEVC is simply unavailable, and **AV1** falls back to CPU software decoding (dav1d).

You are often left with **AVC** only. Yet AVC is the codec with the highest bitrate at the same quality (see §4), so the pressure shifts back onto the network.

### What we observed in the Netherlands case study

The computer in the case study has a GPU with hardware decoding for all three codecs. The problem was a single switch inside the browser:

| Check | Observed value | Meaning |
|---|---|---|
| Setting | "Use graphics acceleration when available" **off** (`hardware_acceleration_mode.enabled = false` in the profile's `Local State` file) | Hardware acceleration disabled |
| GPU process launch flag | `--use-angle=swiftshader-webgl` | WebGL runs on the CPU |
| WebGL renderer | `SwiftShader` | Software rendering |
| `navigator.mediaCapabilities` (1080p60) | HEVC `supported=false`; AVC `smooth=false`; `powerEfficient` is `false` for AVC / HEVC / AV1 | The browser itself reports no hardware decoding, and that even AVC will not play smoothly |
| Video tracks served by Bilibili | AVC only (`codecid 7`) | HEVC and AV1 not usable |

So **CPU software decoding of 1080P60 AVC, plus software compositing, plus danmaku, will stutter no matter how fast the connection is**. Fixing it costs nothing and needs no installs.

### How to check (about 2 minutes)

| Where | What to look at | Fine (hardware) | Problem (software) |
|---|---|---|---|
| `chrome://settings/system` (Edge: `edge://settings/system`) | "Use graphics acceleration when available" (Edge uses the same English wording; the text may differ slightly between versions) | On | Off |
| `chrome://gpu` → "Graphics Feature Status" | *Video Decode*, *WebGL* | *Hardware accelerated* | *Software only* / *Disabled* |
| `chrome://gpu` → GL / ANGLE renderer in the driver information | Renderer name | Your GPU model | Contains *SwiftShader* |
| `chrome://gpu` → "Video Acceleration Information" | Decode entries | `Decode h264 high`, `Decode hevc main`, and on newer GPUs also `Decode av1 profile main` | Empty |
| `chrome://media-internals` → Players → the bilibili entry (start playing a video first) | `kVideoDecoderName`, `kIsPlatformVideoDecoder` | e.g. `D3D11VideoDecoder` + `true` | `Dav1dVideoDecoder` / `FFmpegVideoDecoder` + `false` |
| Windows Task Manager → Performance → GPU → (switch one of the small graphs to "Video Decode") | Video Decode usage during playback | Above 0 | Stays at 0 while the browser's CPU usage is high |

**The easiest way**: on a Bilibili video page, press F12 to open the Console and paste the read-only [`tools/decode-check.js`](../../tools/decode-check.js) (usage notes in [tools/README.en.md](../../tools/README.en.md)). It reports:

- the WebGL renderer, flagging it if it is SwiftShader;
- `supported` / `smooth` / `powerEfficient` for AVC / HEVC / AV1 at 1080p60 and 4K;
- the codec preference you selected in Bilibili's player.

It finishes with a one-line verdict in Chinese and English. The script makes no network requests.

### How to fix

1. Turn on "Use graphics acceleration when available" and **be sure to click "Relaunch"**. Flipping the switch without relaunching has no effect.
2. After relaunching, check `chrome://gpu` again. If the switch is on but you still see SwiftShader or *Software only*, the usual causes are:
   - **An old or known-problematic GPU driver**: look at "Problems Detected" in `chrome://gpu` and update the driver from your GPU vendor's website.
   - **A policy lock**: if `chrome://policy` shows `HardwareAccelerationModeEnabled = false`, it was set by your organisation or by other software; ask your administrator.
   - **Remote desktop or a virtual machine**: these environments often have software rendering only.
3. Laptops: plug in the charger, and turn off "Energy Saver" in `chrome://settings/performance`. Energy Saver lowers video frame rates ([9to5Google](https://9to5google.com/2022/12/08/google-chrome-memory-energy-saver/)) and may switch itself on when you are on battery or the battery is low.

**Firefox users**: in `about:support` → "Graphics", if "Compositing" shows *WebRender (Software)*, rendering is done in software; the "Media" section shows whether each codec supports hardware decoding. Names vary slightly between versions.

## 3. Browser version: auto-update can fail silently

- Open `chrome://settings/help` (Edge: `edge://settings/help`). It checks for and downloads updates; click "Relaunch" when it is done.
- **Auto-update can break quietly without you ever noticing.** For example, on Windows, if the system service that Chrome's updater depends on goes missing, the updater log shows `0x80070424` (`ERROR_SERVICE_DOES_NOT_EXIST`), and the browser may go more than a year without updating, with no warning anywhere in the UI.
- **Fix**: download the installer from the official [google.com/chrome](https://www.google.com/chrome/) and install it over the existing copy. Bookmarks, extensions and sign-in state are kept, and the updater is reinstalled along with it.
- If `chrome://policy` lists update-related policies, updates are being managed by your organisation or by other software.
- **Why it matters**: an old browser misses security patches as well as media-stack fixes. Some userscript-manager features (for example the "Allow User Scripts" toggle required since Chrome 138) also need a recent browser version.

## 4. Codecs: which playback setting to choose

Where: player ⚙ → "More playback settings (更多播放设置)" → "Codec preference (播放策略)". The menu may change between Bilibili versions. The choice is stored in local storage under `bilibili_player_codec_prefer_type`: `0` default, `1` HEVC, `2` AVC, `3` AV1.

| Your situation | Recommendation | Why |
|---|---|---|
| Hardware acceleration works and `chrome://gpu` lists `Decode hevc main` | **HEVC** | Much lower bitrate than AVC; in Chrome, HEVC always uses hardware, so it cannot silently fall back to software decoding |
| You also have `Decode av1 profile main` (roughly: newer discrete and integrated GPUs, e.g. NVIDIA RTX 30 series and later, see the [NVIDIA decode support matrix](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new)) | **AV1** or HEVC | AV1 has the lowest bitrate. But Chrome always reports AV1 as "playable" (via the built-in dav1d software decoder), so always go by `chrome://gpu` |
| Hardware acceleration cannot be fixed | **AVC** (temporarily) | AVC is the lightest to decode in software, but it has the highest bitrate, so unpopular videos lean even harder on the network |

**Do not switch to AVC by default "to be safe".** In the samples listed by BiliLoader, AVC's bitrate is 2.3–2.7 times HEVC's at the same quality:

| Quality | AVC | HEVC | AV1 | Source |
|---|---:|---:|---:|---|
| 1080P | 4.5 Mbps | 1.9 Mbps | ≈2.1 Mbps | [BiliLoader](https://github.com/Phantivia/BiliLoader); AV1 from [BTR #45](https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/45) |
| 1080P 60 fps | 9.9 Mbps | 3.7 Mbps | 3.5 Mbps | [BiliLoader](https://github.com/Phantivia/BiliLoader) |
| 4K | ≈16.5 Mbps | ≈12 Mbps | ≈9 Mbps | [V2EX t/1106060](https://v2ex.com/t/1106060) |

Bitrates vary from video to video. For example, the unpopular video in run 3 of the Netherlands case study was 1080P60 AVC with a declared bitrate of just 3.48 Mbps.

Notes:
- How the player picks a codec when set to "Default" is only described by third parties (reportedly AV1 > HEVC > AVC); there is no official Bilibili source, so **choosing one explicitly** gives you more control.
- Videos with few views may have no HEVC or AV1 version (unverified); go by the Mime Type actually shown in "Stats for nerds (视频统计信息)".

## 5. Other local factors

| Factor | When to suspect it | What to do |
|---|---|---|
| Energy Saver / battery | Laptop unplugged, or battery very low | Plug in; turn off "Energy Saver" in `chrome://settings/performance`; set the Windows power mode to "Best performance" |
| Hybrid graphics (integrated + discrete GPU) | You want a feature specific to one GPU (e.g. NVIDIA RTX Video Super Resolution, VSR) | Usually no change needed; integrated GPUs can normally hardware-decode too. If needed, go to Windows Settings → System → Display → Graphics and set the browser to "High performance" |
| Refresh-rate cadence | No dropped frames, but the picture moves in little jerks | Try switching 144 Hz to 120 Hz or 60 Hz; G-SYNC applies to only one window at a time (per Blur Busters' "G-SYNC 101" guide) |
| NVIDIA RTX Video Super Resolution (VSR) | Frames drop once VSR is on | Set it to "Auto" or turn it off. NVIDIA notes that a quality level above what the system can handle may cause stutter |
| Danmaku | Fine with danmaku off | Lower the danmaku density, or use [pakku.js](https://github.com/xmcp/pakku.js) to merge repetitive (spam) danmaku |
| Extensions / userscripts | Fine in a Guest window | Disable extensions one by one to find the culprit; run only one speed-up script at a time |

## 6. A 3-minute diagnostic routine

Pick one popular video (e.g. BV15KpR6TENe) and one unpopular video (very few views, fairly long, one you have not watched before), and play both at the same quality with the same codec preference. **Do not enable any speed-up script yet.**

| Step | Time | What to do | What to look at |
|---|---|---|---|
| 1 | 40 s | Play 30 s of the popular video and 30 s of the unpopular one | Only the unpopular one stutters: buffering. Both stutter: decoding or rendering |
| 2 | 30 s | Right-click the video → "Stats for nerds (视频统计信息)" | The codec in Mime Type (`avc1` = H.264, `hev1` / `hvc1` = HEVC, `av01` = AV1), Resolution, Video DataRate, Video Speed, Video Host, Dropped Frames |
| 3 | 30 s | Run [`decode-check.js`](../../tools/decode-check.js), or look at `chrome://gpu` | Whether hardware acceleration is actually in effect (§2) |
| 4 | 45 s | `chrome://media-internals` → Players → bilibili | `kIsPlatformVideoDecoder` = `true` means hardware decoding |
| 5 | 30 s | F12 → Network → type `m4s` into the filter box | Domain is the node actually in use; Waiting (TTFB) of each request. If every segment of the unpopular video waits 1–2 seconds and throughput is low, it is a CDN origin-fetch problem |
| 6 | 30 s | Turn danmaku off; then open a Guest window and play the same unpopular video | Fine with danmaku off: danmaku load. Fine only in the Guest window: an extension |

**How to decide**

| Symptoms | Verdict |
|---|---|
| Spinner; sound and picture stop together; Video Speed below about 1.5× Video DataRate; Dropped Frames not rising | **Buffering (network)** → [02](02-why-cdn.md) |
| No spinner; sound continues while the picture stutters; buffer bar far ahead; Dropped Frames keep rising (above 1%, or several frames per second) | **Decoding / rendering** → fix it with §2–§5, and you are done |

To record the numbers objectively, paste the read-only [`tools/play-monitor.js`](../../tools/play-monitor.js). It records time to first frame, the number and duration of stalls, the wait after seeking, and dropped frames.

**Checkpoint**: after all this you should be able to write one sentence like: "It's buffering: only unpopular videos stutter, Video Speed is below DataRate, no dropped frames, hardware decoding works." Or: "It's decoding: ..."

---

Next: [02 · Why only unpopular videos spin](02-why-cdn.md)
