# 05 · Safe install of BTR: pin the version, turn off updates, exclude sensitive subdomains

[简体中文](../zh-CN/05-safe-install.md) · **English** · [← Back to home](../../README.en.md)

> **First make sure you really need it.** Work through the [60-second checklist](../../README.en.md#60-second-checklist) on the home page (hardware acceleration above all), then use [`cdn-bench.js`](../../tools/cdn-bench.js) to confirm that unpopular videos really are held up by the CDN ([02 §8](02-why-cdn.md#8-test-it-yourself)). If switching to another node on a single connection is enough, the lightweight realzza script may be less hassle (§6.1).
>
> The recipe on this page applies only to the audited commit `0302b34` (v2026.10.8.1). UI labels are tagged:
> - **[checked against docs]**: verified against official documentation or source code;
> - **[UI not verified]**: written from experience; the actual wording may differ slightly.

```
Prepare (§1) → pinned install (§2 Tampermonkey or §3 Violentmonkey) → verify → first-time setup → A/B test (§5)
             → passes: everyday use (§7); fails: alternatives (§6)
```

## 1. Prepare

1. **Browser up to date, hardware acceleration on** ([01](01-diagnosis.md)).
2. **Use only one userscript manager**: either Tampermonkey (stable) or Violentmonkey, not both:
   - A script installed in two managers is injected twice.
   - **Avoid Tampermonkey BETA** unless you really need it: the official docs state that `GM_cookie` reading httpOnly cookies (such as your login session) is supported only in the BETA ([docs][tm-cookie]).
   - Make sure the extension is the official one: `chrome://extensions` → Details; the ID in the address bar should be that of Tampermonkey stable, `dhdgffkkebhmkfjojejmpbldmpobfkfo` ([TM FAQ Q406][q406]).
3. **Turn on "Allow User Scripts"**: `chrome://extensions` → your script manager → Details. Required since Chrome 138 ([TM FAQ Q209][q209]).
4. **Disable any other Bilibili speed-up scripts or extensions** (realzza, MBGTEB, CDN switchers, the old BTR extension, etc.).
5. **Measure a baseline first**: with [`cdn-bench.js`](../../tools/cdn-bench.js) (how to run it: [tools/README.en.md](../../tools/README.en.md)), test 1 popular video and 1 unpopular video you have **never watched** (logged in, at the quality you normally use), and save the results.

## 2. Install recipe: Tampermonkey (Chrome / Edge)

**① Open the install URL pinned to the commit.** Do not use the button in BTR's README, which points to `main`.

```
https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js
```

This URL is addressed by commit hash, so its content can never change: it is exactly the audited file (blob `0dd5d9c`). Tampermonkey will open its install page.

> For an extra check: save the file at this URL and compute its SHA-256. On Windows use `certutil -hashfile <file> SHA256`; on macOS / Linux use `shasum -a 256 <file>`. The result should be `7766622730f6d24febb89cd3669ff0c384997c260c652668082d84af61724dd9` (405,714 bytes, LF line endings).

**② Check the install page**, and click "Install" only if everything matches [UI not verified]:

- The name is `Bilibili 线程撕裂者` (Bilibili Thread Ripper) and the version is **`2026.10.8.1`**.
- The match pattern is only `https://*.bilibili.com/*`.
- **Exactly 6** grants: `GM_registerMenuCommand`, `GM_addElement`, `unsafeWindow`, `GM.getValue`, `GM.setValue`, `GM_addValueChangeListener`.
- **No** `@require`, `@resource`, `@connect`, `GM_xmlhttpRequest` or `GM_cookie`.
- `@updateURL` / `@downloadURL` point to `…/main/…`: this is expected; you will turn them off in the next step.
- You will also see `@run-at document-start`, `@sandbox JavaScript`, `@inject-into content`, an `@icon` pointing to main, and descriptive fields such as `@namespace`, `@homepageURL` and `@supportURL`. These are expected too. The first three only decide when the script runs and in which execution context; they are not extra permissions. The icon is just an image.

**If anything does not match, do not install.**

**③ Turn off automatic updates for this script.** Do both A and B; C is an extra safeguard:

- **A [checked against docs]** Dashboard → click "Bilibili 线程撕裂者" to open the editor, change the `@updateURL` and `@downloadURL` lines in the header (lines 11–12) to the following, then save (Ctrl+S). The official docs state that no update check is made when `@downloadURL` is set to `none` ([docs][tm-dl]).

  ```
  // @updateURL    none
  // @downloadURL  none
  ```

- **B [required; UI not verified]** Open this script's "Settings" tab, untick "Check for updates" (检查更新) and save.
  > Why A alone is not enough: in a test on Tampermonkey 5.5.1 (2026-10-13), after doing only A, Tampermonkey's internal record showed `updateURL` as `none`, but `downloadURL` still held the original `…/main/…` address from installation, and "Check for updates" was still ticked. Rather than rely on how Tampermonkey interprets `none`, switch this off too.
- **C [setting confirmed by the maintainer, location not verified]** Tampermonkey Settings → switch "Config mode" to "Advanced" → "Script Update" → set the check interval to "Never" ([issue #1753][tm1753]). **Note: this affects all your scripts.**

**④ Exclude sensitive subdomains** [checked against docs: `@exclude` takes precedence over `@match` ([docs][tm-ex]); for user excludes see [FAQ Q103][q103]]. Pick one:

- In the same edit as ③A, add these lines below the `@match` line:

  ```
  // @exclude      https://passport.bilibili.com/*
  // @exclude      https://pay.bilibili.com/*
  // @exclude      https://account.bilibili.com/*
  // @exclude      https://member.bilibili.com/*
  ```

- Or add these 4 addresses one by one under the script's "Settings" → "User excludes" (用户排除).

> ⚠️ Mind the line breaks when pasting: every `// @…` line must be on its own line. If you paste a block whose last line has no trailing newline, it gets glued to the next line, `// @run-at       document-start`. We hit exactly this in testing: `@run-at document-start` stopped working and the last exclude rule broke. Before saving, check that `// @run-at` is still on its own line.

BTR has no function on these subdomains anyway. Once they are excluded, even a bad version cannot touch the login, top-up and account pages. Keep www, m, live and space: you need them to watch videos. Note that www pages also contain a login pop-up, so the exclusions only **reduce** the risk; pinning the version is what really matters.

**⑤ Verify.** Today `main` and the pinned version are the same file, so "no new version found when checking for updates" proves nothing. Check each item below instead:

- Close and reopen the dashboard, open the script editor, and confirm that lines 11–12 still say `none` (so the save took effect).
- "Check for updates" is unticked (③B).
- In the editor, `// @run-at       document-start` is still on its own line, and each of the 4 `@exclude` rules is on its own line.
- The dashboard shows version `2026.10.8.1`.
- Open any video: BTR's floating button (悬浮球) appears on the page; right-click the player → "Stats for nerds (视频统计信息)", and Player Type shows `BTR Native`.
- Open `https://passport.bilibili.com/login` and type `document.documentElement.hasAttribute('data-btr-userscript')` in the F12 console. The result should be `false`, which means the exclusion works.

**⑥ First-time setup:**

- **Explicitly** set "Codec preference (播放策略)" to HEVC (or to AV1 if your GPU can decode AV1 in hardware); do not leave it on "Default (默认)". BTR follows this setting ([source][btr-codec]). On "Default" it tries AV1 > HEVC > AVC, judged only by `isTypeSupported` ([source][btr-order]), and on a computer without AV1 hardware decoding that can end up as CPU software decoding.
- In BTR's settings panel, turn on "Show errors (显示错误)", so that takeover failures (including the retry loop, see [03 §7](03-btr-security-audit.md#7-cookie-carrying-retry-loop-low-severity-bug)) no longer happen silently.
- Leave "Live acceleration (experimental) (直播加速（实验性）)" off. Keep the other defaults for now (mainland nodes, automatic thread count, full takeover), then go to §5.

**⑦ Make a note**: install date, source (commit `0302b34`), version number.

## 3. Install recipe: Violentmonkey

For people who prefer Violentmonkey, the manager BTR recommends, or who use NVIDIA RTX Video Super Resolution (VSR): one user reported that BTR stops VSR from working under Tampermonkey but not under Violentmonkey ([#46][b46], not fixed). **This replaces Tampermonkey; it is not an addition**: keep only one manager enabled at a time. The UI labels below are taken from Violentmonkey's own locale files (English, with the Simplified Chinese in parentheses); its update behaviour (checks daily by default and updates **silently**) also comes from its source code.

1. Disable other script managers and install Violentmonkey; in `chrome://extensions` → Violentmonkey → Details, turn on "Allow User Scripts".
2. Open the pinned commit URL from §2 ① to install; check the version 2026.10.8.1, the match pattern and the 6 grants (as in §2 ②).
3. Dashboard → BTR → Edit → "Settings (设置)" tab:
   - untick "Allow update (允许更新)";
   - fill in both "Update URL: (检查更新地址：)" and "Download URL: (下载更新地址：)" with the pinned commit URL, so that even a manual update click fetches the same file;
   - add the 4 addresses from §2 ④ under "@exclude-match rules (@exclude-match 规则)".

   Save.
4. Verify: reopen the script's "Settings" and confirm that "Allow update" is unticked and both update URLs are the pinned commit URL; the version is 2026.10.8.1; `data-btr-userscript` is `false` on the passport page.
5. First-time setup: same as §2 ⑥.

## 4. Upgrading safely later

1. **Don't chase new versions**: upgrade only when you need a specific fix. When a new version is released, wait at least a week and check the [issues][issues] for problem reports.
2. In the [commit history of the release file][hist], find the new release commit and copy its **full** hash, written `<NEW>` below.
3. Open `https://github.com/MrTangLuyao/Bilibili-thread-ripper/compare/0302b345cdfe367ac599b52dc6874e3f7967e220...<NEW>` and **focus on the changes to the release file `user_scripts/bilibili-thread-ripper.user.js` itself**. CI does not check that it matches src/; see [03](03-btr-security-audit.md), finding S7.
4. In the diff, use Ctrl+F to search for each of the following:
   - **Header**: `@match`, `@include`, `@exclude`, `@grant`, `@connect`, `@require`, `@resource`, `@updateURL`, `@downloadURL`, `@run-at`
   - **Account-related**: `document.cookie`, `cookieStore`, `bili_jct`, `SESSDATA`, `DedeUserID`, `csrf`, `passport`, `login`, `POST`, plus any newly added `credentials: "include"`
   - **Exfiltration or code execution**: `sendBeacon`, `WebSocket`, `EventSource`, `new Image`, `eval`, `new Function`, `atob`, `import(`, `Worker`, `innerHTML`, `GM_xmlhttpRequest`, `GM_cookie`, `GM_download`
   - **New domains**: any `https://` literal outside bilibili.com / bilivideo.* / hdslb.com / akamaized.net / github; large base64 blobs, long runs of `\x` / `\u` escapes, whole lines of minified code
5. If you cannot follow it, or something looks suspicious: don't upgrade yet. Ask a friend who reads code to review it, or use AI code-review tools to do a rebuild comparison, a keyword scan and a read of the diff.
6. Once it passes: open `https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/<NEW>/user_scripts/bilibili-thread-ripper.user.js` to install over the old version, then **redo §2 ②–⑤** (for Violentmonkey, §3 steps 2–4), because the new file points to main again and has no exclusion rules.

## 5. A/B test: find the settings that work best for you

**Fixed conditions**: the same browser window; laptop plugged in; VPN / WARP / proxy off; BTR is the only speed-up tool enabled; the quality you normally watch at (ideally 1080P or higher); a fixed codec preference; danmaku (bullet comments) off while measuring.

**Videos**: H is one popular video; C1…C6 are six **different** unpopular videos, because an unpopular video becomes "hot" once you have tested it. Alternatively, use one very long unpopular video and in each round jump to a position that has **never been played** (for example 10, 20, 30, 40 minutes in).

**Each round** (about 4 minutes):

1. Turn off "Autoplay (自动开播)" in the player, then press F5 to reload.
2. Paste [`play-monitor.js`](../../tools/play-monitor.js) into the console, then press play.
3. Watch for 3 minutes, seeking twice, both times to parts you have not watched.
4. Type `__pm.stop()` in the console.

Meanwhile, keep an eye on Video Speed and Video DataRate in "Stats for nerds (视频统计信息)", and on "current total threads (目前总线程)" in the BTR panel.

| Round | BTR setting | Videos |
|---|---|---|
| V0 baseline | BTR off (master switch in the floating-button panel) | C1 + H |
| V1 | Mainland (大陆) + automatic thread count + full takeover (全接管) (default) | C2 + H |
| V2 | Overseas (海外) + automatic thread count + full takeover | C3 + H |
| V3 | Custom (自定义): tick the 4–6 fastest nodes from cdn-bench's unpopular-video test, from different vendors where possible (hw and 08c are both Huawei and share a set of IPs), e.g. ali, hw, cos, bd, plus automatic thread count | C4 + H |
| V4 | The best of V1–V3, switched to "Compatibility mode (兼容模式)" | C5 + H |
| V5 (optional) | The best setting, with the codec preference switched between HEVC and AV1 | C6 + H |

- Keep the thread count on "automatic". Try a fixed 16 only if you see 412 / 429 errors or high CPU usage.
- Enter only `*.bilivideo.com` hosts as custom nodes.
- If you want popular videos to keep using the Akamai node Bilibili assigned (not verified): in V3, use "Add manually (手动添加)" to add the host name of **your** assigned primary node (the `分配-主` (assigned primary) row in the cdn-bench table), and do not enter any other akamaized.net host. Inferring from the source code ([cdn-resolver.js][btr-custom]), some addresses will be disabled after Akamai rejects them (403) ([disable rule][btr-ban]); this is expected and harmless.

**Pass criteria** (check them in every round)

| Metric | Pass | Where to look |
|---|---|---|
| Download speed on unpopular videos | Video Speed stays ≥ **1.5×** Video DataRate throughout the 3 minutes | Stats for nerds |
| Stalls (excluding seeks) | **0** (1 is borderline, 2 or more fails) | play-monitor |
| Wait after seeking | ≤ 3 s each time | play-monitor |
| Time to first frame | Popular: at most 1.5 s slower than V0; unpopular: no slower than V0 | play-monitor |
| Dropped-frame rate | < 1% | play-monitor / Stats for nerds |
| No new problems | Quality switching, danmaku, auto-play next (自动连播), multi-part videos (分P), collections (合集), loop, playback speed, fullscreen, keyboard shortcuts, HDR / Dolby (if available) and RTX VSR (if used) all work normally | Manual check |
| No regression on popular videos | 0 stalls, startup not noticeably slower | play-monitor |

**How to choose**: among the settings that pass everything, pick the one with the fewest side effects; when two are about equal, prefer "Compatibility mode" and fewer custom nodes. If **V0 already passes**, you don't need BTR for now; uninstall it as described in §7.

**Log sheet**

| Round | Video | Quality / codec | Video Speed ÷ DataRate | Stalls / total s | Seek wait | First frame ms | Dropped-frame rate | New problems | Pass? |
|---|---|---|---|---|---|---|---|---|---|
| V0 | C1 | | | | | | | | |
| V0 | H | | | | | | | | |
| V1 | C2 | | | | | | | | |
| V2 | C3 | | | | | | | | |
| V3 | C4 | | | | | | | | |
| V4 | C5 | | | | | | | | |
| V5 | C6 | | | | | | | | |

## 6. Alternatives if it doesn't pass (in this order)

For the full comparison see [04 · Alternatives](04-alternatives.md). **Only ever run one speed-up tool at a time.**

### 6.1 realzza Bilibili Accelerator (single-connection node switching, fewest permissions)

Suits two situations: cdn-bench shows that a single connection to another node is enough; or BTR's takeover breaks features you need.

- Disable or delete BTR first.
- Install: make sure it is [Greasy Fork #582026][rzgf] (author realzza; #588296 is a different script with the same name), or [v0.5.0][rzrel] on GitHub. Check for `@grant none` and version 0.5.0.
- As in §2 ③A and ③B, change `@updateURL` and `@downloadURL` to `none` and untick "Check for updates"; then add the 4 `@exclude` lines from §2 ④, because its match pattern also covers passport and the other subdomains.
- What to expect: popular videos stay on their original node; how much unpopular videos improve depends on its candidate node pool (which has no 08c). We only spot-checked it (it does not access cookies, contacts no third-party endpoints, and the release file is a concatenation of the source); we did not do a full audit.

### 6.2 MBGTEB 1.9.0, with only Thread Ripper on

For when both BTR's full takeover and its compatibility mode have problems you cannot live with.

- Disable BTR or realzza first.
- Install from a version-pinned URL (on npm, the content of a published version number cannot be changed):

  ```
  https://unpkg.com/make-bilibili-great-than-ever-before@1.9.0/dist/make-bilibili-great-than-ever-before.user.js
  ```

  Then turn off updates as in §2 ③A and ③B.
- In the script manager's menu, **turn on** Thread Ripper (off by default) and **turn off** other modules that change behaviour, at least: "force 4K", which spoofs the user agent; "disable AV1" (if you can decode AV1 in hardware); and the module that wraps localStorage (menu names not verified).
- Risks: this module was merged only recently, by the author themselves, with no public benchmark data, and we have not audited it. Run the same A/B test as in §5.

### 6.3 Offline: a third-party downloader or the official client

- **[Bili23-Downloader][b23] ≥ 2.20.0**: the fastest way to download unpopular videos for offline viewing. Set the region **manually** to CN, move ali / hw to the top, and set the thread count to 8–10. ⚠️ It stores SESSDATA in **plain text** in config.json under AppData; log out in the app when you are not using it. Personal offline viewing only.
- **Offline cache in the official client**: the most reliable option and adds no new risk, but it is not any faster. Cache unpopular videos in advance.

### 6.4 Advanced (not verified): route only the video domains through a Hong Kong / Japan relay

Only consider this if you **already have** a trustworthy direct node in Hong Kong or Japan. Key points:

- keep www.bilibili.com and api.bilibili.com on DIRECT;
- point `DOMAIN-SUFFIX,bilivideo.com`, `DOMAIN-SUFFIX,bilivideo.cn` and the **exact host name** of your assigned Akamai primary node to a rule group `[DIRECT, HK, JP]`, and switch it manually per video (DIRECT for popular videos);
- **never** write `DOMAIN-SUFFIX,akamaized.net`;
- pin rule-set URLs to a specific commit;
- use the latest version of your proxy client.

For details see [04 §C](04-alternatives.md#c-network-layer).

## 7. Everyday use and uninstalling

**Everyday use**

- **Only ever run one speed-up tool.**
- **Don't click update**: keep BTR pinned, and review per §4 before upgrading.
- **When a video won't play** (region-locked, supporters only (充电专属), 412 errors or a CAPTCHA): close that tab, or temporarily turn BTR off with the master switch in the floating-button panel, to avoid the retry loop that sends cookies ([03 §7](03-btr-security-audit.md#7-cookie-carrying-retry-loop-low-severity-bug)).
- **Never post full `.m4s` URLs publicly**: they contain `mid` (your UID) and `oi` (your IP). cdn-bench results and BTR's "Copy diagnostics (复制诊断信息)" contain neither.
- **Check once a quarter**: whether BTR's issues contain reports of "risk control (风控)" or "account bans (封号)"; whether your browser and script manager are up to date; whether hardware acceleration is still on (a browser reset or a driver update can turn it off).

**Uninstalling BTR cleanly**

1. Script manager dashboard → BTR → Delete (if there is a recycle bin, empty it too).
2. Optional: F12 → Application → Local Storage → `https://www.bilibili.com` (and m, live), delete the keys starting with `BTR` (`BTR_Userscript.sync`, `BTR_Userscript.local`, `BTR.codecFailuresCleared`). Leaving them is harmless.
3. If you want, set the codec preference back to what it was before.
4. If you previously installed the old Chrome extension version ("Bilibili 线程撕裂者" loaded in developer mode), remove it in `chrome://extensions`.
5. Open a video and confirm that Player Type in "Stats for nerds (视频统计信息)" is back to `DashPlayer`.

---

Previous: [04 · Alternatives](04-alternatives.md) · [Back to home](../../README.en.md)

<!-- Links -->
[q406]: https://www.tampermonkey.net/faq.php?locale=en&q=Q406#Q406
[q209]: https://www.tampermonkey.net/faq.php?locale=en&q=Q209#Q209
[q103]: https://www.tampermonkey.net/faq.php?locale=en&q=Q103#Q103
[tm-cookie]: https://www.tampermonkey.net/documentation.php?locale=en&q=GM_cookie#api:GM_cookie.list
[tm-dl]: https://www.tampermonkey.net/documentation.php?locale=en&q=update_url#meta:downloadURL
[tm-ex]: https://www.tampermonkey.net/documentation.php?locale=en&q=include#meta:exclude
[tm1753]: https://github.com/Tampermonkey/tampermonkey/issues/1753
[b46]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/46
[btr-codec]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L1111-L1116
[btr-order]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/native-mse-player.js#L84-L90
[btr-custom]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/cdn-resolver.js#L61-L92
[btr-ban]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/cdn-resolver.js#L109-L178
[issues]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues
[hist]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/commits/main/user_scripts/bilibili-thread-ripper.user.js
[rzgf]: https://greasyfork.org/scripts/582026
[rzrel]: https://github.com/realzza/bilibili-accelerator/releases/tag/v0.5.0
[b23]: https://github.com/ScottSloan/Bili23-Downloader
