# 04 · Alternatives compared

[简体中文](../zh-CN/04-alternatives.md) · **English** · [← Back to README](../../README.en.md)

> Research date: 2026-10-13. We looked at five areas (in-browser, desktop clients, community experience, network layer, decoding), and each area had its own independent fact-checker. **The tables have been rewritten with the fact-checkers' corrections**; where the two disagreed, the fact-check wins. Star counts, install counts and dates are as of that day and will change.
>
> Apart from BTR (see [03](03-btr-security-audit.md)), the options here were **only fact-checked and keyword-scanned, not audited to the same depth**. Every issue listed below is something we observed at a point in time, or something the code does, with a source attached. None of it is a judgement of the authors. Thanks to the authors of these projects for publishing their code.

**Legend** (for the problem "unpopular videos stutter outside China"): ✅ addresses it　⚠️ partly helps　❌ does not address it　❓ unverified

**First, a recap of the bottleneck** ([02](02-why-cdn.md)): on overseas edges (Akamai / cosov / aliov), unpopular (cold) videos have to be fetched back from origin, and that is slow. "Mainland nodes + parallel connections" held steady at 24–26 Mbps. Popular videos don't stutter in the first place. Also, **rule out the local hardware-acceleration problem first** ([01](01-diagnosis.md)); no script can fix that.

## A. In the browser (userscripts / extensions)

| # | Option | ⭐ / installs | Last activity | Mechanism | Fits the problem? | Risk | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | [BTR][btr], pinned to `0302b34` | 1.2k★ | 2026-10-10 | Full takeover (feeds MSE itself) or compatibility mode; mainland / overseas / custom nodes; automatic 8–64 threads; hedged retries; 45 s read-ahead | ✅ Matches "mainland + parallel" exactly. But mainland mode drops the Akamai node Bilibili assigns, so popular videos may start a little more slowly | Unpinned: auto-update (medium); pinned: low. Full-takeover mode has historically seen more regressions ([#28][b28] and [#46][b46] are still open) | **First choice** (audited, [03](03-btr-security-audit.md)) |
| 2 | [MBGTEB][mbg] 1.9.0, Thread Ripper module (by SukkaW) | 727★ | Merged 2026-10-10 | Only rewrites XHR / fetch, does not take over the player; benchmarks every mirror (Akamai included) for each video; at most 6 concurrent requests per host and 32 in total; overlapping bytes returned by different hosts are cross-checked | ✅ Right design, less invasive; @match only covers www / t / live / space | The module was merged by the author himself with 0 reviews and has no public benchmark data yet ([PR #31][mbg31]); **about 15 other modules are on by default** (they spoof a macOS Safari UA, disable AV1, wrap localStorage, block telemetry, etc.); auto-updates from unpkg `@latest` (npm releases carry SLSA provenance, which lowers the risk) | **Fallback**; re-evaluate once real-world feedback exists |
| 3 | [realzza Bilibili Accelerator][rz] v0.5.0 | 602★ · [Greasy Fork #582026][rzgf] about 4.7k installs | 2026-09-28 | Starts on the node Bilibili assigns; if it measures that node can't keep up with the bitrate (or there is no first byte within 1 s), it races 2 candidate nodes and switches only if one is at least 1.5× faster; **single connection** | ⚠️ Popular videos stay on the original node (good); how much unpopular videos improve depends on whether the candidate pool contains a fast enough node. The pool is fixed: cosov, aliov, hwov, ali, tf-all-hw, hw, cos, tf-all-tx, **with no 08c**; in the Netherlands case ali and hw gave 4–7 Mbps on a single connection | Lowest privileges (`@grant none`, contacts no third-party endpoints, the release file is just the source files concatenated; the Greasy Fork and GitHub versions are byte-identical apart from the two update-URL lines); but @match includes passport and every other subdomain; Greasy Fork auto-updates; the author has published US West Coast measurements ([vod-routing.md][rzdoc]) | **Lightweight choice** (when cdn-bench shows a single connection is enough) |
| 4 | [Bilibili Video CDN Switcher][gf500] (Greasy Fork #500213) | about 13.7k installs | 2026-08-25 | Rewrites playback URLs to one fixed host | ⚠️ No picker UI: to change host you edit the `CustomCDN` variable in the source; by default only the primary URL is rewritten, so when the primary is Akamai you also have to enable "Replace backup playback URLs" (替换备用播放地址); pinning one mainland host slows down popular videos | No license ("Free For Personal Use"); it also replaces the page's XHR and fetch | Temporary diagnosis only |
| 5 | [Overseas Video Speedup][ovs] (海外视频加速) | 16★; about 5k users per third-party stats (may be out of date) | 2026-10-12 | 300 nodes, per-country presets, optional automatic switching | ❌ Presets only cover TW / SG / HK / JP / AU / US; every other country (e.g. the European ones) falls back to the Taiwan preset; it starts rewriting segment URLs as soon as it is installed, without measuring first; single connection | When you file a bug report, diagnostic data (IP, ISP, province, IDs of videos watched in the last 10 minutes) is sent to the developer's private repository (only when you choose to submit; see its PRIVACY.md); for the companion CDNSpeedTest.exe see §F; the MPL-2.0 shown on AMO doesn't match the custom license in the repository | Not recommended |
| 6 | [CCB][ccb] (Custom CDN of Bilibili) | 220★ · Greasy Fork about 4.1k | Code 2026-08-07 | Fetches a node list from the author's GitHub Pages; you pin one node by hand | ❌ [#15][ccb15] (open): the default node can't be replaced when it is Akamai / cosov, which is exactly the assignment in the Netherlands case; "stopped working" reports in 2026-09 | Uses `GM_xmlhttpRequest`; the remote list is only checked for format; injects code into Web Workers; the README says the code was written by AI | Not recommended |
| 7 | [Bili Turbo][turbo] | 0★ | 2026-10-10 (a single commit) | 4 parallel connections to hw / 08c / ali / cos | ❌ Judging from the code, after in-site navigation the Akamai-to-bilivideo mapping stops working, so all 4 connections go to Akamai (the worst case for cold content) | No license; accepts HTTP 200 as a Range response (may write wrong data); loaded unpacked by hand and never updates | Not recommended |
| 8 | Other niche projects: [BiliLoader][bl] (pre-warms overseas edges; too slow in Europe), [Bili Pilot][pilot] (only uses the URLs Bilibili assigns), [liiliiliil][lii] (doesn't handle akamaized.net), [zk39][zk39] (unmaintained), [BiliKit][bkit] (fixed mainland node), [SanJerry007][sj] (prefers Akamai), [stabruriss][stab] (overseas routes only), PCDN blockers (viewers outside China are rarely assigned PCDN anyway) | — | — | — | ❌ | — | Not recommended |
| 9 | BTR forks, [BiliThrottle][thr] (a repackaged BTR) | 0–2★ | — | Same as BTR | — | All behind upstream; the repackage has not been audited | Not recommended |

## B. Desktop clients and downloaders (Windows)

| # | Option | ⭐ | Last activity | Mechanism | Fits the problem? | Risk | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Official client + offline cache (离线缓存) | Closed source | — | Playback is single-connection, like the web player (not fully verified) | ⚠️ Online playback won't be faster; good for "download first, watch later" | First-party login, adds no new exposure; cached files only play inside the client | First choice for offline (zero added risk) |
| 2 | [Bili23-Downloader][b23] v2.20.0 | 8.3k★ | 2026-09-27 | Strips PCDN, swaps hosts from an editable list, 4 threads per file (up to 10) | ✅ Fast offline downloads of unpopular videos. But you **must** manually set the region to CN, move ali / hw to the top and raise threads to 8–10; otherwise an overseas exit IP is auto-detected and the overseas list (aliov, cosov) is used | SESSDATA is stored in **plain text** in config.json under AppData; version 2.15 was once flagged by antivirus (a false positive); according to its CI configuration and release notes, builds are code-signed from 2.20 on; downloaders have been discontinued after lawyers' letters before | First choice for offline (third-party) |
| 3 | [PiliPlus][pili] 2.1.6.x | 19.4k★ | 2026-10-12 | mpv playback; 21 selectable CDNs; can benchmark **the current video** inside the player | ⚠️ Single connection; switching host starts from the Akamai signed URL and may return 403 ([#3242][pili3242]); not enough for unpopular 4K | Can play 1080P without logging in (incognito / guest mode (无痕 / 游客模式), so no SESSDATA is handed over); after login the token is stored unencrypted; the Windows build is unsigned; there is a Windows frozen-picture issue (#2700); its predecessor PiliPala received an infringement notice | Worth a try (1080P) |
| 4 | [lemonteaau/PiliPlus][lemon] (BTR port) | 9★ | 2026-10-12 | Local 127.0.0.1 Range proxy + BTR core | ❓ Right design, but not yet verified on a real network; "Overseas nodes" (海外节点) is on by default | A personal, AI-assisted fork; merges upstream and publishes a release automatically every day, without review; unsigned | Experimental |
| 5 | [BBDown][bbd] 1.6.3 | 13.9k★ | Archived 2026-05-14 | `--upos-host` + multiple threads | ⚠️ Works, but is no longer maintained | Defaults to `--force-http` and sends cookies with every media request, so when logged in your SESSDATA travels in **plain text**; `serve` mode is an unauthenticated API that accepts any origin, which a web page can abuse to make your computer run arbitrary programs | Only logged out and with `--force-http false`; **never use `serve`** |
| 6 | yutto, yt-dlp, Gopeed extension, bilibili-tui, mpv + cdn-router | — | Active | Only use the URLs Bilibili assigns, or a single connection | ❌ | yt-dlp's `-N` has no effect on Bilibili's single-file streams; aria2c with multiple connections to Akamai is actually worse ([02 §5](02-why-cdn.md#5-what-the-three-unpopular-videos-have-in-common)) | Not recommended (for this problem) |
| 7 | BTR desktop version, [Lanes][lanes] | — | — | Modify or inject into the official client | — | Desktop version: see [03 §8](03-btr-security-audit.md#8-desktop-version-and-old-chrome-extension-use-caution); Lanes opens a debugging port, so any process on your computer can control your logged-in session | Not recommended |
| 8 | DownKyi, downkyicore, BiliTools, BilibiliDown | — | Discontinued 2026-07 | — | — | Discontinued after lawyers' letters (the repositories still exist but are marked deprecated or archived); installers re-uploaded elsewhere can't be trusted | Not recommended |

## C. Network layer

| # | Option | ⭐ / last activity | Mechanism | Fits the problem? | Risk | Verdict |
|---|---|---|---|---|---|---|
| 1 | Route **only the video domains** through a Hong Kong / Japan relay (e.g. a mihomo or Clash Verge Rev rule group `[DIRECT, HK, JP]`) | mihomo 34.8k★ · Clash Verge Rev 150.9k★ · Hysteria 22.7k★ (all active) | www / api stay direct (the region Bilibili sees doesn't change); the relay resolves the video hosts from Asia and carries the long-haul leg | ❓ **Unverified hypothesis**; assumes you already have a trustworthy direct HK / JP node; switch popular videos back to DIRECT | Clash Verge Rev ≤ 2.5.4 has a local privilege-escalation vulnerability ([advisory][cvr]; use ≥ 2.5.8); if you self-host Hysteria, run the latest server version; signed URLs contain `oi` (your IP), so changing the exit may return 403 (untested); mihomo is actually GPL-3.0 and its default branch holds unrelated content, so download from Releases | Advanced; try it last |
| 2 | Public rule sets (blackmatrix7, ACL4SSR, v2fly, elysias123) | blackmatrix7 28.2k★ · v2fly 9.7k★ · ACL4SSR 6.8k★ · elysias123 30★ | Just the "plumbing" | — | blackmatrix7's rule content stops at 2025-06; ACL4SSR's Hong Kong / Macau / Taiwan rules stop in 2023; elysias123's example REJECTs Akamai; most rule sets lump www / api together with public DNS IPs | Use only [v2fly][v2fly]'s `geosite:bilibili-cdn` plus the exact Akamai hosts; write your own DIRECT rule for www / api; pin rule URLs to a specific commit |
| 3 | "Return-to-China" accelerators (回国加速器; various commercial products) | Commercial, closed source | Make Bilibili treat you as a mainland user | ❌ What you get is a long-haul mainland route plus PCDN, with no independent benchmarks at all | The mainland operator can see all traffic in the tunnel; your IP location and the content you can watch change; auto-renewal is common | Not recommended (unless you need content licensed only for mainland China) |
| 4 | Gaming accelerators, general-purpose VPNs | Commercial, closed source | Wrong direction | ❌ | Often kernel-driver-level software | Not recommended |
| 5 | Self-built mainland exit (a relative's home broadband, a Chinese cloud server) | — | Same as 3 | ❌ | Legal grey area; unusual upload traffic on a home line may get it blocked | Not recommended |
| 6 | Pinning IPs in the hosts file ([akamTester][akt] etc.), DNS / ECS tricks | akamTester 376★ (unmaintained since 2025-03) | Only swaps one edge IP for another | ❌ Outside China, Akamai usually already resolves to a local node; low latency ≠ high throughput; pinning across CDNs simply fails TLS | Requires editing system files; akamTester is unmaintained and its latest binary is an unsigned exe from 2020 | Not recommended |
| 7 | MITM rewrite modules ([Biliverse/Redirect][bvr] etc.) | 22★ | The proxy app rewrites CDN URLs | Not applicable to Chrome on Windows | Requires trusting a root certificate; one Shadowrocket variant sends signed URLs containing `mid` / `oi` to a third-party endpoint (leaking your viewing history) | Not recommended |
| 8 | Watching Bilibili with Cloudflare WARP on | Cloudflare, official | Swaps your exit for a Cloudflare one | ❌ Doesn't change the node Bilibili assigns and adds a detour ([WARP FAQ][warp]) | — | Turn it off while testing and watching Bilibili |
| 9 | Windows TCP "optimisers", BBR2, disabling QUIC | — | Change local transport parameters | ❌ Congestion control in the download direction is decided by the CDN server ([RFC 9438 §5.10][rfc]); BBR2 on Windows 11 24H2 can hang local proxies | Changes system settings | Not recommended (disabling QUIC at most as a one-off A/B test) |

## D. Settings and diagnostics (zero risk, do these first)

| Option | What it does | Notes | Verdict |
|---|---|---|---|
| **Turn on browser hardware acceleration** | Hardware decoding, hardware compositing | Cause A in the Netherlands case; see [01 §2](01-diagnosis.md#2-step-one-is-hardware-acceleration-on) | **Must do** |
| Set "Playback strategy (播放策略)" to HEVC or AV1 | Lowers the bitrate you need | Chrome plays HEVC only with hardware decoding; choose AV1 only if `chrome://gpu` lists `Decode av1 profile main`; at the same quality, AVC needs 2.3–2.7× the bitrate of HEVC | Must do |
| Hardware-decode self-check: `chrome://gpu`, `chrome://media-internals`, [`decode-check.js`](../../tools/decode-check.js) | Rules out decode stutter | Method based on [StaZhu's guide][stazhu] (1.45k★) | Must do |
| [`cdn-bench.js`](../../tools/cdn-bench.js) (this repo; see [tools/README.en.md](../../tools/README.en.md)) | Compares cold / popular, single / parallel connections, and each node | Approach inspired by [chrisliu298's probe.js][cl] | Recommended |
| Bilibili's official [diagnostics page][diag] (add `?bvid=…&cid=…`) | First-party speed test | Only tests the start of the file, on a single connection, so it understates the cold-content problem; without parameters it requires login and reads your watch history | For reference |
| NVIDIA: set VSR to Auto or Off; check G-SYNC windowed mode; switch 144 Hz to 120 / 60 Hz | Rendering and frame pacing | Only helps with "dropped frames or judder, but no buffering spinner" | Depends on the case |
| [pakku.js][pakku] | Merges floods of repeated danmaku (bullet comments) | Only helps if "turning danmaku off fixes it" | Depends on the case |
| Bilibili-Evolved, enhanced-h264ify, BewlyBewly | — | None of them has playback-CDN or codec settings; h264ify only targets YouTube and is unmaintained; BewlyBewly is archived | Not relevant |

**Projects unmaintained for more than 12 months**: the original Make BiliBili Great Again (2024-12), AkagiYui's PCDN blocker (2024-10), Bilibili-Old (2024-09), akamTester (2025-03). Greasy Fork #553929 (2025-10) is close to that too.

## E. Legal and longevity risks

Over the past year, Bilibili's law firm has sent letters to a number of third-party projects: PiliPala (2025-07), bilibili-API-collect (2026-01, archived afterwards), BiliRoaming (2026-07-06; the letter lists "rewriting the CDN origin to misappropriate the platform's distribution resources" as one of the issues, [source][roam]), and DownKyi, downkyicore and BiliTools (2026-07-06, discontinued afterwards).

**BTR, realzza, CCB and MBGTEB all belong to this category of scripts that rewrite CDN addresses.** This means:
- They may stop working or be taken down at any time. If you install a pinned version, your userscript manager keeps its own copy.
- Using them **may not comply with Bilibili's user agreement**. Make your own judgement.

Pure routing approaches (§C-1) don't rewrite addresses and are not in this category.

## F. Not recommended, and why

| Not recommended | Why |
|---|---|
| BTR desktop version | Installed with `irm … \| iex`; the EXE is unsigned; needs UAC elevation; starts at boot; updates are checked only against hashes in the same repository; the maintainer suggests turning off Smart App Control; you don't need it to watch Bilibili in a browser ([03 §8](03-btr-security-audit.md#8-desktop-version-and-old-chrome-extension-use-caution)) |
| Old BTR Chrome extension zip / .crx from Releases | Discontinued, doesn't auto-update, not verified byte for byte; running it alongside the userscript means two takeovers at once |
| CDNSpeedTest.exe (companion to [Overseas Video Speedup][ovs]) | Based on the README and code under `tools/cdn-speedtest-app` in its repository: built on the developer's own machine and can't be reproduced from source; requires Bilibili QR-code login; uploads your exit IP, city, ISP, network type (including Wi-Fi details) and usage records; looks up your IP over plain HTTP; reads browser profile files; updates itself; tied to a giveaway campaign |
| Commercial "return-to-China" accelerators, gaming accelerators, general-purpose VPNs | Don't fix slow cold-content origin fetches; a third party sees all your traffic; your region changes; PCDN is actually slower |
| Pinning IPs in the hosts file, akamTester, DNS / ECS tricks | Low latency ≠ high throughput; fails outright across CDNs; requires editing system files |
| Watching Bilibili with WARP on | Doesn't change the assigned node, only makes it slower |
| BBDown `serve`; the default `--force-http` while logged in | The unauthenticated API can be abused by web pages to run local programs; SESSDATA travels in plain text |
| Running two speed-up tools at once (BTR + MBGTEB Thread Ripper / realzza / a CDN switcher) | They all modify the same media requests, so they fight each other and the results can't be interpreted |
| Lanes | Opens a debugging port; any process on your computer can control your Bilibili session |
| Self-built mainland exit | The legal and account-ban risk falls on whoever provides the exit |
| BTR repackages and unmaintained scripts (BiliThrottle, the original MBGA, AkagiYui, Bilibili-Old, GF #553929) | Not audited, or no longer maintained |
| Greasy Fork #588296 | A separate, unrelated script that is also called "Bilibili Accelerator"; to install realzza, make sure it is [#582026][rzgf] |
| Windows TCP "optimisers", BBR2 | No effect on downloads; they may also switch off window auto-tuning or hang local proxies |

---

Previous: [03 · BTR security audit](03-btr-security-audit.md) · Next: [05 · Installing BTR safely](05-safe-install.md)

<!-- links -->
[btr]: https://github.com/MrTangLuyao/Bilibili-thread-ripper
[b28]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/28
[b46]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/46
[mbg]: https://github.com/SukkaW/Make-Bilibili-Great-Than-Ever-Before
[mbg31]: https://github.com/SukkaW/Make-Bilibili-Great-Than-Ever-Before/pull/31
[rz]: https://github.com/realzza/bilibili-accelerator
[rzgf]: https://greasyfork.org/scripts/582026
[rzdoc]: https://github.com/realzza/bilibili-accelerator/blob/main/docs/vod-routing.md
[gf500]: https://greasyfork.org/scripts/500213
[ovs]: https://github.com/a0972199950/bilibili-cdn-switcher
[ccb]: https://github.com/Kanda-Akihito-Kun/ccb
[ccb15]: https://github.com/Kanda-Akihito-Kun/ccb/issues/15
[turbo]: https://github.com/sfeng77/bili-turbo
[bl]: https://github.com/Phantivia/BiliLoader
[pilot]: https://github.com/siwei-yuan/bili-pilot
[lii]: https://github.com/liiliiliil/bili-cdn-switcher
[zk39]: https://github.com/zk39/bilibili-cdn-switcher
[bkit]: https://github.com/shiinayane/BiliKit
[sj]: https://github.com/SanJerry007/bilibili-cdn-optimizer
[stab]: https://github.com/stabruriss/bilibili-accelerator
[thr]: https://github.com/ooooooomygosh/Better-Bilibili
[b23]: https://github.com/ScottSloan/Bili23-Downloader
[pili]: https://github.com/bggRGjQaUbCoE/PiliPlus
[pili3242]: https://github.com/bggRGjQaUbCoE/PiliPlus/issues/3242
[lemon]: https://github.com/lemonteaau/PiliPlus
[bbd]: https://github.com/nilaoda/BBDown
[lanes]: https://github.com/ChiaWei0804/Lanes
[cvr]: https://github.com/clash-verge-rev/clash-verge-rev/security/advisories/GHSA-99qg-xv7m-jf4v
[v2fly]: https://github.com/v2fly/domain-list-community
[akt]: https://github.com/miyouzi/akamTester
[bvr]: https://github.com/Biliverse/Redirect
[warp]: https://developers.cloudflare.com/warp-client/known-issues-and-faq/
[rfc]: https://www.rfc-editor.org/rfc/rfc9438.html
[stazhu]: https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding
[cl]: https://github.com/chrisliu298/bilibili-cdn-fix
[diag]: https://www.bilibili.com/blackboard/video-diagnostics.html
[pakku]: https://github.com/xmcp/pakku.js
[roam]: https://github.com/yujincheng08/BiliRoaming
