# 03 · BTR (Bilibili Thread Ripper) security audit

[简体中文](../zh-CN/03-btr-security-audit.md) · **English** · [← Back to home](../../README.en.md)

> Audit date: 2026-10-13 · Covers **only** commit [`0302b34`][c] (version 2026.10.8.1) · Any later update has **not been audited**
>
> BTR is developed by [MrTangLuyao](https://github.com/MrTangLuyao) and released as open source under the MIT License. Thanks to the author for publishing the source, and for keeping the build reproducible: that is what made an audit like this possible. This is an independent third-party reading with no affiliation to the author. It is **neither an endorsement nor a security guarantee**. If you find a mistake here, please open an issue.

## Bottom line first

| Question | Answer |
|---|---|
| Does this code do anything malicious? | **We found nothing malicious.** The released file matches the source byte for byte. It does not read cookies, does not send data out and does not load remote code. The only requests sent with your login are 3 read-only GETs, the same ones Bilibili's own player makes. |
| What is the main risk? | **Silent auto-update when the version is not pinned.** The script auto-updates daily from the `main` branch, and that branch has **no branch protection, with at least 2 accounts able to push to it**. If that channel is ever compromised, new code runs on every Bilibili page you open, as you. Almost every userscript that auto-updates from GitHub raw has this problem, so it is not unique to BTR, but what is at stake is your Bilibili account. |
| Anything else? | All **low** severity: a cookie-carrying retry loop with no cap (about 1 request per second under specific conditions); injection into subdomains it has no use for, such as login and payment; a settings channel with no authentication; a fairly broad "Custom CDN" allowlist; and so on. |
| Can I use it? | **Yes, but pin the version.** Follow [05 · Safe install](05-safe-install.md): pin the commit, turn off update checks, and exclude passport / pay / account / member. Do not install the desktop version, and do not install the old Chrome extension zip from Releases. |

## 1. What was audited

| Item | Value |
|---|---|
| Repository | [MrTangLuyao/Bilibili-thread-ripper](https://github.com/MrTangLuyao/Bilibili-thread-ripper) (MIT, created 2026-08-27; about 1.2k★ and 31 forks at audit time) |
| Commit | `0302b345cdfe367ac599b52dc6874e3f7967e220` (2026-10-09 UTC, i.e. 2026-10-10 UTC+8). This commit changes only the README and one image, with no code changes. The previous release commit is `c283962`, and between the two only the README and images changed as well. |
| Install file | [`user_scripts/bilibili-thread-ripper.user.js`][hdr] · git blob `0dd5d9c` · 405,714 bytes (LF line endings) · SHA-256 `7766622730f6d24febb89cd3669ff0c384997c260c652668082d84af61724dd9` |
| Re-checked on the day | On 2026-10-13, remote `main` still pointed to `0302b34`, and the raw URL served exactly this blob |

## 2. Method

This audit was **carried out with the help of AI code-review agents**: 33 independent review tasks in total, 23 of them focused on BTR and the other 10 used to research alternatives (see [04](04-alternatives.md)). It is not an audit by a professional security firm. Every conclusion links to source code at a fixed commit, and anyone is welcome to re-check it.

| Group | Tasks | What it did |
|---|---:|---|
| Dimension audits | 7 | Network egress, code execution and injection, build integrity, privacy and account, reputation and supply chain, red-team backdoor hunt, effectiveness |
| Adversarial review | 12 | For every "medium" finding, 2 independent reviewers tried to refute it or adjust its severity |
| Completeness review | 1 | Looked for gaps and proposed 3 follow-up tasks |
| Follow-up investigations | 3 | ① Worst case of a malicious update, and how to pin the version; ② distribution channels (old extension zip, social media reposts); ③ trigger conditions and frequency of the cookie-carrying retry loop |

Main techniques:
- **Byte-for-byte rebuild**: about 10 independent rebuilds, done by reimplementing `scripts/build.mjs` in Python, **without running any code from the repository**. The rebuilt install file is **byte-for-byte identical** to the released one, and the same holds for all 7 releases since 2026.9.27.1.
- **Full read** of the 15 bundled source files, plus item-by-item searches for every egress method (fetch / XHR / WebSocket / sendBeacon / Image / script / iframe, etc.) and every obfuscation marker (eval, new Function, atob, invisible or bidirectional characters, long base64).
- **git and the GitHub API**: authors and committers, signatures, branch protection, and who merged each PR and with what review record (shallow clone of the latest 50 commits, going back to 2026-09-19).
- **Measured external conditions**: CSP response headers on 13 Bilibili pages; update defaults in the Violentmonkey source; Tampermonkey's official documentation.
- **Not done**: running repository code; downloading the old extension zip; logging in to Bilibili for runtime observation.

## 3. Results by dimension

| Dimension | Result | In one line |
|---|---|---|
| Network egress | ✅ Clean | Connects only to api.bilibili.com and Bilibili's video CDN; no telemetry; diagnostics go only to the clipboard, with query strings stripped |
| Code execution / injection | ⚠️ Minor | No eval, no remote code; the whole engine runs with the page's identity and updates along with main (a trust issue, not a vulnerability) |
| Build integrity | ⚠️ Minor | Build output matches the source, but CI does not verify the committed release file |
| Privacy / account | ⚠️ Minor | Does not touch cookies; has one cookie-carrying retry loop with no cap (low) |
| Reputation / supply chain | ⚠️ Minor | Author identity is consistent, no signs of malice; main is unprotected, at least 2 accounts can write to it, PRs have no review record |
| Red team | ⚠️ Minor | No backdoor found; the risk lies in future updates |
| Follow-up: worst case | ⚠️ Minor | Safe today; **only pinning the version and turning off updates keeps it safe later** |
| Follow-up: distribution channels | ⚠️ Minor | The social media reposts we saw all link only to the official repository, but the "Latest" release is still the discontinued extension zip |
| Follow-up: retry loop | ⚠️ Minor | Confirmed; severity set to low |

## 4. Findings (final severity after review)

| # | Finding | Final | Evidence | Notes |
|---|---|---|---|---|
| S1 | Auto-update points at the mutable `main`: no branch protection, unsigned release commits, at least 2 accounts can push | **Medium** | [Header L11-12][hdr-upd] · [release.mjs L85][release] · [PR #25][pr25] | Of 8 independent review opinions, 6 rated it "low", on the grounds that almost every userscript updates this way; the follow-up investigation quantified the worst case and kept it at "medium". We use "medium" because what is at stake is your Bilibili account. See §6 |
| S2 | Also injects into subdomains such as passport / pay / account / member (it has no function on these pages) | Low | [@match L13][hdr-match] · [L31][frame] · [page-hook L16-17][host-gate] · [native-mse-player L1348-1351][installs] | Today it only passively installs a few patches there, but if a bad version ever ships, it would be present on the login, top-up and account pages |
| S3 | When play info cannot be read, the cookie-carrying view / playurl requests retry with no cap (about once per second) | Low | [L1283][gate] · [L1328-1335][catch] · [L1570-1582][tick] | Initially rated "medium"; both reviewers and the follow-up investigation agreed to lower it to "low". See §7 |
| S4 | The CustomEvent channel between the page and script storage has no authentication | Low | [loader.js L43-55][bridge] | Any script on the same page can change BTR's settings (changes are re-validated afterwards; there is no path to code execution) |
| S5 | The "Custom CDN" allowlist covers all of `*.akamaized.net` plus PCDN vendor domains | Low | [range-core L5][allow] · [L77-84][norm] | Only takes effect in "Custom" mode |
| S6 | Global patches change what Bilibili itself records and reports | Low | [native-mse-player L344-370][setitem] | During takeover, 5 decode-failure keys are not written and 2 kinds of player errors are swallowed; no values are read or sent out |
| S7 | CI does not verify that the committed release file equals the source | Low | [userscript-test L20-25][pubtest] | When reviewing an upgrade, read the diff of the release file itself, not just src/ |
| S8 | Far more requests to the CDN than the native player makes (auto 8–64 threads, up to 128 manually, plus hedged duplicate requests) | Low | [L139-148][ladder] · [L632-635][pushback] | No cookies, so at worst it triggers IP-level rate limiting; auto mode steps down on 412 / 429, manual mode does not |
| S9 | Uses the older unsigned (non-WBI) API | Low | [page-hook L705-758][api] | Read-only GETs with normal parameters; only the request fingerprint differs from the official player |
| S10 | Merged PRs have no review record; before 2026-09-27, external PRs modified the release file directly | Low | [PR list](https://github.com/MrTangLuyao/Bilibili-thread-ripper/pulls?q=is%3Apr) | Since then, the release file has been modified only by the maintainer's release commits |
| S11 | The "Latest" GitHub release is still the discontinued Chrome extension zip (0.9.4.3, not verified byte for byte) | Low | [Releases][releases] · [README L71][readme-ext] | The author's README already asks users to remove the old extension |
| S12 | The distribution channel of BTR's desktop version carries higher risk | Medium (desktop version only) | [Desktop repository][desk] · [desktop #5][desk5] | Users of the browser script only are unaffected (both reviewers rated it "low" for userscript-only users; "medium" applies to the desktop version only). See §8 |
| S13 | Pages can detect it, which can be used for fingerprinting (an attribute on `<html>` contains the script manager's name and version) | Info | [loader.js L85-93][loader-start] | Only a read-only marker, not tracking |
| S14 | A test switch, `__BTR_TEST_ALLOW_LIVE__`, remains in production code | Info | [live-hook L7][livegate] | A page is very unlikely to be able to set it in time; impact is negligible |
| S15 | Installing by commit SHA does **not** pin the version: the header still points at `main` | Info (critical) | [Header L11-12][hdr-upd] | So you must also turn off update checks when installing ([05](05-safe-install.md)) |
| S16 | None of the 13 Bilibili pages we tested enforce a CSP (3 of them send Report-Only only) | Info | Response headers measured in the follow-up investigation | This amplifies S1: if a bad version sends data out, the browser will not block it |

## 5. What it accesses, and what it does not

**Network destinations**

| Destination | When | Cookies sent? | Content |
|---|---|---|---|
| `api.bilibili.com`: `/x/web-interface/view`, `/x/player/playurl`, `/pgc/player/web/v2/playurl` | When the page has no DASH info ready (in-site navigation, refreshing signatures) | Yes (same as Bilibili's own player) | Only bvid / aid / cid / ep_id; on a normal first page load, not a single request |
| `*.bilivideo.com` / `.cn` video nodes ([built-in list][lists], addresses assigned by Bilibili, addresses you set yourself) | During playback | **No** (`credentials:'omit'`, Referer is the origin only, [L596-606][cdn-fetch]) | Range GET |
| `upos-*.akamaized.net` assigned by Bilibili | Overseas or custom mode; in mainland mode, possibly only for reading the index at startup | No | Range GET |
| `<link rel=preconnect>` to the nodes above | On page load | No | Connection setup only |
| `raw.githubusercontent.com` | When the script manager checks for updates or fetches the icon | — | Initiated by the manager, not by the script's own code |

**What it does**: reads the video fields in `__INITIAL_STATE__` and `__playinfo__`; reads its own settings from localStorage, along with `bilibili_player_codec_prefer_type` ([L1111-1116][codec-pref]) and the autoplay preference; saves settings in GM storage; wraps fetch / XHR ([observing playurl only][wrap]), history, `Storage.setItem`, `URL.createObjectURL` and `SourceBuffer.buffered`; when you click the button, writes diagnostics (with query strings stripped) to the clipboard; the live-stream module (off by default) blocks Bilibili's P2P SDK.

**What it does not do**:
- Does not read `document.cookie`, and does not touch SESSDATA, bili_jct, DedeUserID or buvid;
- No POSTs: no likes, coins (投币), follows or comments;
- No `GM_xmlhttpRequest`, `@connect`, `GM_cookie` or `@require`;
- No telemetry, no third-party endpoints;
- No eval, no remote code loading;
- Does not forge WBI signatures or change the UA;
- Does not bypass membership, region or DRM restrictions.

**Traces it leaves**: `sync` in GM storage; `BTR_Userscript.sync`, `BTR_Userscript.local` and `BTR.codecFailuresCleared` in localStorage on each subdomain; attributes such as `<html data-btr-userscript …>`; globals such as `window.__biliThreadRipperDebug`.

## 6. The main risk: silent auto-update when not pinned

**Who can release**: the repository owner, plus at least 1 collaborator with push access (see the merge record of [PR #25][pr25]: merged locally, commit unsigned). The `main` branch is `protected:false` and its rulesets are empty; HEAD and the release commits are unsigned (only a few web-UI merge commits carry GitHub's automatic signature) and the release tags are lightweight. The release script itself says that pushing to main is the same as shipping to all users ([release.mjs L85][release]).

**How fast a new version reaches you**: raw.githubusercontent caches for 5 minutes, and the script manager checks once a day, so it arrives within about 1 day.
- **Violentmonkey** (the manager BTR recommends) checks once a day by default, with `notifyUpdates:false`. Even header changes (`@match`, `@grant`) are applied silently ([source][vm-defaults]).
- **Tampermonkey**: according to the maintainer's explanation in a GitHub issue, a confirmation page appears only when include / match / exclude, connect or the update URLs change; code-only changes install silently (we did not re-verify this in the current version). The official documentation confirms that `@downloadURL none` turns off update checks ([docs][tm-dl]); however, in a test on Tampermonkey 5.5.1 its internal record still kept the original download address after the change to `none`, so the install guide also requires switching off the script's "Check for updates" (see [05 ③B](05-safe-install.md)).

**What a bad version could do without changing the header** (this is a thought experiment, not verified by an actual attack):
1. **Act as you on the website**: page code can read the non-HttpOnly `bili_jct` cookie (Bilibili's own player uses it to fill in `csrf`), so it could post comments, send danmaku, send private messages, follow, like and give coins, edit your profile and delete content, and it could also read your history, favorites and private messages. Whether it could make payments directly was **not tested**.
2. **Exfiltrate data**: none of the 13 pages enforce a CSP, so `fetch`, `sendBeacon` and `new Image()` can all send data to any server.
3. **Delayed session hijacking**: SESSDATA is HttpOnly and cannot be read. But community-maintained API documentation shows that the JSON returned by the login endpoint contains session information ([source][apicollect]). BTR already wraps the page's fetch / XHR (currently filtering for playurl only), so a bad version would only need to widen the filter to possibly capture your session **the next time you log in**. On passport pages, it could also record the password and verification code you type.
4. **If the header changes too**: Violentmonkey silently accepts `@match` being widened to every website. Tampermonkey's documentation states that `GM_cookie` in the **BETA** version can read httpOnly cookies ([docs][tm-cookie]). So unless you really need it, do not use Tampermonkey BETA.

**Likelihood and impact**: the likelihood is low. The author's identity is public and consistent, star growth lines up with the release of [the author's introduction video][promo] ([Trendshift][trend]), and there are no signs of malice. But the impact is high, because your Bilibili account is involved.

**Countermeasures**: pin the commit, turn off update checks, exclude sensitive subdomains, and review the diff before upgrading. See [05 · Safe install](05-safe-install.md) for how.

## 7. Cookie-carrying retry loop (low-severity bug)

- **Mechanism**: when BTR fails to read play info itself, the [catch branch][catch] only schedules a retry and does not mark the failure; the [1-second timer][tick] then calls `startPlayer` directly; and [the only flag that would make it stop][gate] (`failedRoute`) is never set on this failure path. [`recordTakeoverFailure`][fail] only decides whether to show an error; it has neither a cap nor backoff.
- **Frequency**: about 60 attempts per minute in a foreground tab. If the first request fails, that is about 60 cookie-carrying requests per minute; if view succeeds and playurl fails, about 120 per minute. After 5 minutes, Chrome throttles background tabs to about 1 per minute ([Chrome timer throttling][throttle]). Multiple tabs multiply this.
- **Trigger conditions** (all must hold at the same time):
  - the page has a player `<video>` wider than 200px;
  - there is no cached DASH info;
  - BTR's own request failed;
  - Bilibili's own playurl also gets no DASH.

  In practice, this means **a video you could not watch anyway** (region-locked, or for paying channel supporters only (充电专属)), or **your IP has already been flagged by Bilibili's risk control (412)**. On a normal video page load there are 0 extra requests; on in-site navigation there is 1 view plus 1 playurl, cancelled as soon as Bilibili's own response arrives.
- **Silent by default**: "Show errors (显示错误)" is off by default ([runtime-notices L36-38][errnotice]).
- **Consequence**: most likely, a temporary IP-level 412 lasts longer. There are currently no reports of any account-level penalty (this point is speculation).
- **Countermeasure**: turn on "Show errors (显示错误)" in BTR's settings. For videos that are region-locked, will not open or ask for a captcha, **close that tab or temporarily disable BTR**.
- **Suggested upstream fix**: set `failedRoute` after N failures, or add exponential backoff.

## 8. Desktop version and old Chrome extension: use caution

- **BTR desktop** ([repository][desk], modifies the official Windows client):
  - installed via `irm … | iex`; the EXE is unsigned, there is no CI, and the packaged zip is committed directly to the repository;
  - requires UAC elevation, and the elevation step executes JS from the user-writable `%LOCALAPPDATA%` directory;
  - writes an HKCU autostart entry; updates rely only on a SHA-256 checksum stored in the same repository;
  - in [desktop #5][desk5] the maintainer suggested "temporarily turning off Smart App Control". If you have already turned it off, since a 2026-04 Windows update you can turn it back on without reinstalling Windows ([source][sac]).

  If you watch Bilibili in a browser, you do not need the desktop version.
- **Old Chrome extension zip / .crx** (the "Latest" entry on [Releases][releases] is still 0.9.4.3): discontinued, does not auto-update, and we did not verify it byte for byte; the author asks users to remove it in [README L71][readme-ext]. If you previously installed the "Bilibili 线程撕裂者" (Bilibili Thread Ripper) extension in developer mode, remove it at `chrome://extensions`, and **do not run it at the same time as the script version**.
- **Unofficial channels**: BTR is not listed on Greasy Fork or in any store ([#24][i24]); the only official channel is GitHub. Forks and ports that use the same name are not official.

## 9. Reputation and community signals

- The author's GitHub account dates back to 2020, and the author's identity on GitHub and Bilibili is public and consistent (for example, the [introduction video][promo] the author published). We found no donation or monetization links.
- The star curve lines up with the introduction video published on 2026-09-16 ([Trendshift][trend]), which does not look like star farming.
- All 26 issues filed by audit time (open and closed) are about functionality; we saw no reports of stolen accounts, bans or risk-control actions. But the repository dates from 2026-08-27 and has been in wide use for only about 4 weeks (since the 2026-09-16 video), so this is weak evidence.

## 10. Limitations of this audit

- **Covers only `0302b34`**; any later commit needs a fresh audit.
- Purely static audit: request frequency was not observed on real pages, and the retry-loop frequency comes from reasoning about the control flow.
- Shallow clone, so history before 2026-09-19 was not reviewed; collaborator permissions and branch-protection details are visible only through public signals.
- Not verified: the update-prompt behavior of the current Tampermonkey version, whether region-locked pages render a `<video>`, and whether payments require extra confirmation.
- The old extension zip was not downloaded and verified.
- Alternatives (MBGTEB, realzza, etc.) only received fact-checking and keyword scans, not an audit of the same depth.

---

Previous: [02 · Causes and benchmarks](02-why-cdn.md) · Next: [04 · Alternatives](04-alternatives.md)

<!-- Links (all BTR source links are pinned to commit 0302b34) -->
[c]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/commit/0302b345cdfe367ac599b52dc6874e3f7967e220
[hdr]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js#L1-L23
[hdr-upd]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js#L11-L12
[hdr-match]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js#L13
[frame]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js#L31
[bridge]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/adapter/loader.js#L43-L55
[loader-start]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/adapter/loader.js#L85-L93
[host-gate]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L16-L17
[fail]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L118-L150
[wrap]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L618-L650
[api]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L705-L758
[codec-pref]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L1111-L1116
[gate]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L1283-L1285
[catch]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L1328-L1335
[tick]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/page-hook.js#L1570-L1582
[allow]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/range-core.js#L5
[norm]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/range-core.js#L77-L84
[lists]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/cdn-resolver.js#L7-L23
[cdn-fetch]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/idm-downloader.js#L596-L606
[ladder]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/idm-downloader.js#L139-L148
[pushback]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/idm-downloader.js#L632-L635
[setitem]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/native-mse-player.js#L344-L370
[installs]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/native-mse-player.js#L1348-L1351
[livegate]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/live-hook.js#L7
[errnotice]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/src/runtime-notices.js#L36-L38
[release]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/scripts/release.mjs#L85
[pubtest]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/dev/userscript-test.js#L20-L25
[readme-ext]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/blob/0302b345cdfe367ac599b52dc6874e3f7967e220/README.md?plain=1#L71
[pr25]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/pull/25
[i24]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/24
[releases]: https://github.com/MrTangLuyao/Bilibili-thread-ripper/releases
[desk]: https://github.com/MrTangLuyao/Bilibili-thread-ripper-desktop
[desk5]: https://github.com/MrTangLuyao/Bilibili-thread-ripper-desktop/issues/5
[sac]: https://blog-en.topedia.com/2026/04/smart-app-control-in-windows-11-can-now-be-re-enabled-without-reinstalling/
[promo]: https://www.bilibili.com/video/BV1Teec6BE3s
[trend]: https://trendshift.io/repositories/246040
[vm-defaults]: https://github.com/violentmonkey/violentmonkey/blob/master/src/common/options-defaults.js
[tm-dl]: https://www.tampermonkey.net/documentation.php?locale=en&q=update_url#meta:downloadURL
[tm-cookie]: https://www.tampermonkey.net/documentation.php?locale=en&q=GM_cookie#api:GM_cookie.list
[apicollect]: https://github.com/pskdje/bilibili-API-collect/blob/HEAD/docs/login/login_action/password.md
[throttle]: https://developer.chrome.com/blog/timer-throttling-in-chrome-88
