# 02 · Why only unpopular videos spin: overseas CDN cold cache and benchmarks

[简体中文](../zh-CN/02-why-cdn.md) · **English** · [← Back to README](../../README.en.md)

> **In short**: popular videos hit the cache on overseas edge nodes, so they load fast. Unpopular ("cold") videos are not cached on overseas edges, so every piece of data has to be fetched from the origin in mainland China. Bilibili's web player opens only 1 connection per segment and does not switch nodes just because a node is slow, so all you get is the spinner. All 3 unpopular videos in the Netherlands case study follow this pattern: **the overseas nodes Bilibili assigned stay far below the bitrate, while "mainland nodes + parallel" holds steady at 24–26 Mbps.**
>
> Want the mechanics behind these numbers (signed URLs, cache tiers, TCP at 250 ms, how BTR schedules its requests)? See [06 · Technical deep dive](06-technical-deep-dive.md).

## 1. How it works

```
Popular video:   you ──a few ms──▶ local overseas edge (already cached) ──────────────────────▶ starts instantly
Unpopular video: you ──a few ms──▶ local overseas edge (not cached) ──200–330 ms × every request──▶ origin in mainland China
```

- **Segmented download**: Bilibili's web player uses DASH. The video is cut into many small segments, and each segment is downloaded with an HTTP Range request. The page receives a "primary URL" and a "backup URL". In the Netherlands case study the primary was Akamai (`upos-hz-mirrorakam.akamaized.net`) and the backup was `upos-sz-mirrorcosov.bilivideo.com` (an overseas node).
- **One connection, no switching just because it is slow**: the player opens only 1 connection per segment ([BTR README](https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/README.md?plain=1#L112)) and switches nodes only on an error or a timeout, never because the speed is low ([realzza's measurement notes](https://github.com/realzza/bilibili-accelerator/blob/main/docs/vod-routing.md)).
- **Cold data has to come from the origin**: when the edge node has no cached copy, every request first goes to the origin. We measured a time to first byte (TTFB) of about 2 seconds, and very low throughput.
- **Why "parallel" helps**: the bottleneck is the server-side origin fetch for each request. When several requests fetch from the origin at the same time, the total speed goes up. On a popular video, parallel downloads gave almost no gain (see §4), which shows the benefit is concentrated on cold data.
- **Why "mainland nodes" help** (inference): the content already lives in mainland China. A mainland node is far from you (200–330 ms round trip), but its own path back to the origin is much shorter.
- **Why Douyin does not stutter** (inference): Douyin's web video domain `v3-web.douyinvod.com` lands on the same Alibaba Cloud edge in the Netherlands (as its response headers show). But Douyin videos are short, popular and low-bitrate, and the next ones are preloaded continuously, so they almost always hit the cache. The difference is content popularity, not the route.

## 2. Netherlands case study: test setup

| Item | Setting |
|---|---|
| Location | Netherlands (Western Europe) |
| Device | Windows 11 laptop |
| Network | **No** VPN, WARP or proxy during the tests |
| Date | 2026-10-13, 3 runs on the same day |
| Method | Range requests with `fetch` from inside a `www.bilibili.com` video page; `cache:'no-store'`; no cookies; only bytes from the **middle** of the file that nobody had requested before (cold data), with a different range for each node |
| Switching nodes | Non-Akamai nodes: a Bilibili-signed non-Akamai URL reused with the host name swapped; Akamai was tested only with its own URL |
| Pass mark | A speed of ≥ **1.5×** the video track's bitrate counts as "having headroom" |

| Run | Browser | Logged in | Video | Video track |
|---|---|---|---|---|
| 1 | Another Chromium-based browser on the same computer | No | Popular: BV15KpR6TENe (League of Legends 2026 World Championship trailer); unpopular: BV1xUpZ6NERA (93 views, 47 minutes) | 480P AVC |
| 2 | Same as above, with [`cdn-bench.js`](../../tools/cdn-bench.js) | No | Unpopular: BV1EqYE6iEu5 (64 views, about 3 hours) | 360P AVC, 0.40 Mbps |
| 3 | Everyday Chrome (hardware acceleration was off at the time, see [01 §2](01-diagnosis.md#2-step-one-is-hardware-acceleration-on)), with the benchmark logic of `cdn-bench.js` | **Yes** | Unpopular: BV1wqbT6AEbe (65 views, about 4 hours) | **1080P60 AVC**, declared bitrate **3.48 Mbps**, file about 1494 MB; pass mark = 5.2 Mbps |

## 3. Run 3: logged in, 1080P60 (closest to everyday viewing)

Single connection = one connection downloading 2 MB, which is how Bilibili's own player downloads. 8-way parallel = the same number of bytes split into 8 parts downloaded at the same time, which is how userscripts such as BTR download. "÷bitrate" is the speed divided by 3.48 Mbps; ✅ means ≥ 1.5. In `cdn-bench.js` output, the roles appear in Chinese as 分配-主 (assigned primary), 分配-备 (assigned backup), 海外 (overseas) and 大陆 (mainland).

![Bar chart of run 3: cold-data throughput per CDN node, single connection versus 8 in parallel, with a dashed line at the 5.2 Mbps needed. The assigned Akamai and cosov nodes manage only 0.4 Mbps on one connection (timeout) and under 1 Mbps in parallel; the mainland nodes hw and bd reach 26.3 and 25.5 Mbps with 8 in parallel, and 08c 18.1 Mbps on one connection.](../../assets/cold-throughput-run3.en.svg)

| Node | Role | Single Mbps | ÷bitrate | 8-way parallel Mbps | ÷bitrate | Single TTFB |
|---|---|---:|---:|---:|---:|---:|
| `upos-hz-mirrorakam.akamaized.net` | **Assigned by Bilibili · primary** (Akamai) | 0.4 (timeout) | 0.11 | 0.7 | 0.20 | 2088 ms |
| `upos-sz-mirrorcosov` | **Assigned by Bilibili · backup** (overseas) | 0.4 (timeout) | 0.11 | 0.9 | 0.26 | 502 ms |
| `upos-sz-mirroraliov` | Overseas | 1.0 (timeout) | 0.29 | 3.3 | 0.95 | 920 ms |
| `cn-hk-eq-01-01` | Hong Kong | 1.0 (timeout) | 0.29 | 4.5 | 1.29 | 774 ms |
| `upos-sz-mirrorali` | Mainland | 6.9 | ✅ 1.98 | 11.0 | ✅ 3.16 | 1180 ms |
| `upos-sz-mirrorhw` | Mainland | 6.0 | ✅ 1.72 | **26.3** | ✅ 7.56 | 1206 ms |
| `upos-sz-mirror08c` | Mainland | **18.1** | ✅ 5.20 | 6.0 | ✅ 1.72 | 606 ms |
| `upos-sz-mirrorcos` | Mainland | 2.3 | 0.66 | 7.6 | ✅ 2.18 | 1444 ms |
| `upos-sz-mirrorbd` | Mainland | 4.6 | 1.32 | **25.5** | ✅ 7.33 | 1711 ms |
| `upos-sz-estgoss` | Mainland | 3.9 | 1.12 | 9.7 | ✅ 2.79 | 2802 ms |

**How to read this table**

1. **On unpopular content, the two overseas nodes Bilibili assigned deliver under 1/5 of the bitrate on a single connection (about 0.11×) and under 0.3× even 8-way parallel**, so stutter is unavoidable. Akamai's time to first byte is 2.1 seconds.
2. **Some mainland nodes are enough on a single connection**: 08c (5.2×), ali (2.0×), hw (1.7×).
3. **"Mainland + parallel" has the most headroom**: hw 26.3 and bd 25.5 Mbps, about 5× the 5.2 Mbps pass mark.
4. **Overseas nodes alone are not enough, even in parallel**: the best overseas result is Hong Kong at 4.5 Mbps in parallel, below 5.2.
5. By the rules in `cdn-bench.js`, the verdict for this run is "another node reaches ≥1.5× on a single connection". So for this video, the lighter single-connection CDN-switch userscript (realzza) may be enough, and BTR also works. But in run 2, ali timed out completely: **a single node is not reliable** (see §5).

**After the fix, same video (same day)**: after hardware acceleration was turned on and the browser relaunched, the WebGL renderer changed from SwiftShader to the GPU (D3D11), HEVC and AV1 were decoded in hardware, and the codecs Bilibili served went from AVC only to AVC + HEVC + AV1. With BTR then installed, pinned (full-takeover mode), the video was played at 1080P60 from 10:00, a part nobody had watched before:

| Metric | Result |
|---|---|
| Start after the seek | 3.2 s |
| Stalls in the next 40 s | 0 |
| Forward buffer | 28 s at 5 s; BTR's 45 s cap reached at 10 s |
| Dropped frames | 1 / 2502 (0.04%) |

This is a single playback observation, not a strict A/B comparison. To compare for yourself, follow [05 §5](05-safe-install.md#5-ab-test-find-the-settings-that-work-best-for-you).

## 4. Runs 1 and 2: logged out, low quality

### 4a. Popular video (run 1, BV15KpR6TENe, 480P)

| Node | Role | Single Mbps | 8-way parallel Mbps | TTFB |
|---|---|---:|---:|---:|
| `upos-hz-mirrorakam.akamaized.net` | Assigned · primary | **63.1** | **84.4** | 69 ms |
| `upos-sz-mirrorcosov` | Assigned · backup | 39.3 | 30.7 | 192 ms |
| `upos-sz-mirroraliov` | Overseas | **65.3** | 64.8 | 27 ms |
| `cn-hk-eq-01-01` | Hong Kong | 0.7 | 3.8 | 358 ms |
| `upos-sz-mirrorali` | Mainland | 16.2 | 29.5 | 721 ms |
| `upos-sz-mirrorhw` | Mainland | 18.3 | 18.1 | 242 ms |
| `upos-sz-mirrorcos` | Mainland | 3.6 | 11.9 | 999 ms |
| `upos-sz-mirror08c` | Mainland | 19.7 | 21.8 | 249 ms |
| `upos-sz-mirrorbd` | Mainland | 18.8 | 17.4 | 295 ms |

On the popular video, the assigned Akamai node gave 63 Mbps on a single connection, far above the bitrate of any quality level. So neither the local network nor the last mile is the bottleneck.

### 4b. Unpopular video (run 1, BV1xUpZ6NERA, 480P)

| Node | Role | Single Mbps | 8-way parallel Mbps | Notes |
|---|---|---:|---:|---|
| `upos-hz-mirrorakam.akamaized.net` | Assigned · primary | 3.6 | 0.5 | Single-connection TTFB **2119 ms**; timeouts in parallel |
| `upos-sz-mirrorcosov` | Assigned · backup | Timeout | 0.8 | 2 MB still not finished after 25 seconds |
| `upos-sz-mirroraliov` | Overseas | 0.7 | 3.5 | |
| `upos-sz-mirrorali` | Mainland | 5.3 | **25.7** | |
| `upos-sz-mirrorhw` | Mainland | 4.2 | **26.4** | |
| `upos-sz-mirrorcos` | Mainland | 2.9 | 10.8 | |
| `upos-sz-mirror08c` | Mainland | 8.4 | 6.6 | Parallel was slower (noise) |
| `upos-sz-mirrorbd` | Mainland | — | — | Test script error (range past the end of the file); the new tool handles this |

### 4c. Unpopular video (run 2, BV1EqYE6iEu5, 360P, `cdn-bench.js`)

| Node | Role | Single Mbps | Single TTFB | 8-way parallel Mbps | Notes |
|---|---|---:|---:|---:|---|
| `upos-hz-mirrorakam.akamaized.net` | Assigned · primary | 5.7 | 1792 ms | 7.7 | |
| `upos-sz-mirrorcosov` | Assigned · backup | 2.8 | 837 ms | 3.1 | Network errors in both single and parallel |
| `upos-sz-mirroraliov` | Overseas | 1.2 | 1205 ms | 1.6 | |
| `cn-hk-eq-01-01` | Hong Kong | 0.5 | 1139 ms | 3.4 | Single connection timed out |
| `upos-sz-mirrorali` | Mainland | 0 | — | 0 | **Timed out** in both single and parallel (in run 1 it was one of the fastest) |
| `upos-sz-mirrorhw` | Mainland | 4.6 | 1880 ms | **24.0** | |
| `upos-sz-mirror08c` | Mainland | 7.6 | 1362 ms | 5.0 | |
| `upos-sz-mirrorcos` | Mainland | 2.7 | 1947 ms | 9.0 | |
| `upos-sz-mirrorbd` | Mainland | 2.5 | 2484 ms | 13.7 | |
| `upos-sz-estgoss` | Mainland | 6.0 | 1402 ms | 10.4 | |

This run was logged out and only got 360P (0.40 Mbps), so the tool's verdict was "this video is hot for you". Measured against the roughly 6 Mbps that is typical for 1080P instead: no node reaches 1.5× (9 Mbps) on a single connection; among mainland nodes in parallel, hw (24), bd (13.7) and estgoss (10.4) do. That is why `cdn-bench.js` later gained the `TARGET_MBPS` setting and a low-bitrate warning. **Log in and test at the quality you normally watch.**

## 5. What the three unpopular videos have in common

![Bar chart: the Bilibili-assigned Akamai node on one connection versus the fastest mainland node of each run with 8 in parallel. On the hot video Akamai gives 63.1 Mbps and the fastest mainland node 29.5; on the three cold videos Akamai gives only 3.6, 5.7 and 0.4 (timeout) Mbps, while the fastest mainland node gives 26.4, 24.0 and 26.3 Mbps.](../../assets/hot-vs-cold.en.svg)

| | Run 1 (480P) | Run 2 (360P) | Run 3 (1080P60) |
|---|---|---|---|
| Assigned primary (Akamai): single / TTFB | 3.6 Mbps / 2119 ms | 5.7 Mbps / 1792 ms | 0.4 Mbps (timeout) / 2088 ms |
| Assigned backup (cosov): single | Timeout | 2.8 Mbps | 0.4 Mbps (timeout) |
| Best mainland single connection | 08c 8.4 | 08c 7.6 | 08c 18.1 |
| Best mainland 8-way parallel | hw 26.4 | hw 24.0 | hw 26.3 |
| Best overseas 8-way parallel (incl. assigned nodes) | aliov 3.5 | Akamai 7.7 | Hong Kong 4.5 |

1. **Popular videos play smoothly, unpopular ones stutter**: the same Akamai node gave 63 Mbps on the popular video, but 0.4–5.7 Mbps on unpopular ones, with a wait of about 2 seconds for the first byte.
2. **"Mainland + parallel" is consistent**: across 3 videos and 3 quality levels, the best result was always 24–26 Mbps.
3. **Single mainland nodes are not consistent**: ali gave 5.3 Mbps, a timeout and 6.9 Mbps in the three runs. Approaches that pin one mainland node (the "CDN switcher" kind) are risky; a "multiple nodes + speed test + fallback on failure" design fits better.
4. **Parallel downloads from Akamai on cold data make things worse** (0.5–0.7 Mbps, with timeouts). Do not point multi-connection downloaders such as aria2c `-x16` at Akamai.
5. **The gain from parallelism is concentrated on cold data**: on the popular video, hw, 08c and bd were about as fast in parallel as on a single connection.

## 6. Other network observations (same day, same computer)

- **Round-trip time**: overseas edges 5–12 ms (Akamai's local node in the Netherlands, cosov via EdgeOne, aliov on an Alibaba Cloud node in the Netherlands); mainland upos nodes 215–330 ms (through European internet exchanges, then onto Chinese carriers' international backbones); Bilibili's Hong Kong node about 200 ms, with packet loss.
- **Protocol**: Akamai and estgoss only negotiated HTTP/1.1 (Akamai also advertises HTTP/3); the other upos nodes used HTTP/2.
- **Shared IPs**: hw, 08c, 08h, hwo1 and 08ct resolve to the same set of Huawei GSLB addresses, and cos and coso1 also share IPs. So they are **not independent routes**, and Chrome may also merge hosts with the same IP and certificate onto one connection.

## 7. Why these numbers are only a rough guide

- **Single samples**: each node was measured once per run, and different times of day were not covered. The mainland evening peak is 19:00–23:00 Beijing time, which is 13:00–17:00 Central European Summer Time (12:00–16:00 in winter) and 07:00–11:00 US Eastern Daylight Time. In [realzza's data](https://github.com/realzza/bilibili-accelerator/blob/main/docs/vod-routing.md), the same cold file differed by up to 10× between the mainland evening and the early morning.
- **HTTP/2 multiplexing**: when the browser sends 8 parallel requests to one mainland host, they are really 8 streams on one TCP connection. So the parallel speeds of several nodes **cannot simply be added up**. Numbers from curl with multiple connections will look more optimistic.
- **TCP slow start**: with round trips of 200–330 ms, a 2 MB single-connection sample may not have left slow start yet, so mainland single-connection numbers may read low. You can set `SINGLE_MB` in `cdn-bench.js` to 8 and test again.
- **Testing warms the cache**: only the first read of a byte range is "cold". A re-test needs another video or another range (`cdn-bench.js` randomly offsets its ranges on every run).
- **Regional differences**: other countries may be assigned different nodes. [realzza's notes](https://github.com/realzza/bilibili-accelerator/blob/main/docs/vod-routing.md) also point out that node assignment in Europe and on the US West Coast may differ.

## 8. Test it yourself

1. First read [`tools/README.en.md`](../../tools/README.en.md) and [`tools/cdn-bench.js`](../../tools/cdn-bench.js) (read-only, no cookies, connects only to Bilibili's video CDN).
2. Disable every Bilibili speed-up userscript, and turn off VPN, WARP and proxies. Plug in your laptop.
3. **Log in** and switch to the quality you normally watch. Open a long, low-view video **you have never watched**, press F5, and pause as soon as the picture appears.
4. F12 → Console, paste the script and run it, then wait 1–6 minutes.
5. Read the final "verdict" (结论提示) line:

| Verdict | Meaning | Next step |
|---|---|---|
| The assigned primary node already gives ≥ 1.5× the bitrate on a single connection | This video is "hot" for you; the CDN is not the problem | Go back to [01 · Diagnosis](01-diagnosis.md); no speed-up userscript needed |
| Another node gives ≥ 1.5× the bitrate on a single connection | Switching nodes is enough | The lightweight realzza userscript may be enough; BTR also works ([04](04-alternatives.md), [05](05-safe-install.md)) |
| "Mainland + parallel" reaches ≥ 1.5× the bitrate | You need parallel downloads | BTR, pinned to a fixed version ([05](05-safe-install.md)), or MBGTEB's Thread Ripper module |
| Only "overseas + parallel" reaches ≥ 1.5× the bitrate | You need parallel downloads, but the mainland routes are not good enough | BTR pinned, in overseas mode, or MBGTEB's Thread Ripper module |
| Nothing reaches 1.5× the bitrate | A speed-up userscript cannot help either | Lower the quality, use HEVC / AV1 (if hardware-decoded), or use offline caching |

To save the result, type `copy(JSON.stringify(__cdnBench))` in the console. The result contains no signed URLs and no IP address.

**Please share data from your region** (see [Contributing on the README](../../README.en.md#contributing)). Before sharing, remove full `.m4s` URLs (they contain `mid` = your UID and `oi` = your IP), IP addresses and your precise location.

---

Previous: [01 · Diagnosis](01-diagnosis.md) · Next: [03 · BTR security audit](03-btr-security-audit.md) · Deeper: [06 · Technical deep dive](06-technical-deep-dive.md)
