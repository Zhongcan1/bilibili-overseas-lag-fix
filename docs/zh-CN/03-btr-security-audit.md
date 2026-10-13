# 03 · BTR（Bilibili 线程撕裂者）安全审计

**简体中文** · [English](../en/03-btr-security-audit.md) · [← 返回首页](../../README.md)

> 审计日期：2026-10-13 · **只覆盖**提交 [`0302b34`][c]（版本 2026.10.8.1）· 之后的任何更新都**没有经过审计**
>
> BTR 由 [MrTangLuyao](https://github.com/MrTangLuyao) 开发，以 MIT 许可开源。感谢作者公开源码，也感谢他保持构建可复现，这才让这样的审计成为可能。本文是独立的第三方阅读，与作者无关联，**不构成背书，也不是安全担保**。如果发现本文有误，欢迎提 issue 更正。

## 结论先看

| 问题 | 结论 |
|---|---|
| 这份代码里有恶意行为吗？ | **没有发现。** 发布文件和源码逐字节一致；不读取 Cookie，不外传数据，不加载远程代码。带登录态的请求只有 3 个只读 GET，和 B 站自己的播放器一样。 |
| 主要风险是什么？ | **不钉版本时的静默自动更新。** 脚本每天从 `main` 分支自动更新，而这个分支**没有分支保护，至少 2 个账号能推送**。一旦这个渠道出问题，新代码会在你所有的 B 站页面里以你的身份运行。几乎所有通过 GitHub raw 自动更新的用户脚本都有这个问题，不是 BTR 独有的，但影响面是你的 B 站账号。 |
| 还有别的问题吗？ | 都是**低危**：一个带 Cookie、没有上限的重试循环（特定条件下约每秒 1 次）；在登录、支付等用不到的子域上也会注入；设置通道没有鉴权；“自定义 CDN”的白名单偏宽，等等。 |
| 能用吗？ | **可以，但请钉版本**：按 [05 · 安全安装](05-safe-install.md) 操作，钉死提交、关闭更新检查、排除 passport / pay / account / member。不要装桌面版，也不要装 Releases 里的旧 Chrome 插件 zip。 |

## 1. 审计对象

| 项 | 值 |
|---|---|
| 仓库 | [MrTangLuyao/Bilibili-thread-ripper](https://github.com/MrTangLuyao/Bilibili-thread-ripper)（MIT，2026-08-27 创建；审计时约 1.2k★，31 个 fork） |
| 提交 | `0302b345cdfe367ac599b52dc6874e3f7967e220`（2026-10-09 UTC，即北京时间 2026-10-10）。这个提交只改了 README 和一张图片，没有代码改动。上一个发布提交是 `c283962`，两者之间也只改了 README 和图片。 |
| 安装文件 | [`user_scripts/bilibili-thread-ripper.user.js`][hdr] · git blob `0dd5d9c` · 405,714 字节（LF 换行）· SHA-256 `7766622730f6d24febb89cd3669ff0c384997c260c652668082d84af61724dd9` |
| 当天核对 | 2026-10-13，远端 `main` 仍指向 `0302b34`，raw 地址提供的就是这个 blob |

## 2. 方法

这次审计**借助 AI 代码审查代理完成**：一共 33 个相互独立的审查任务，其中 23 个专门针对 BTR，另外 10 个用于调研替代方案（见 [04](04-alternatives.md)）。它不是专业安全公司的审计。所有结论都附有指向固定提交的源码链接，欢迎任何人复核。

| 组 | 任务数 | 做了什么 |
|---|---:|---|
| 维度审计 | 7 | 网络外联、代码执行和注入、构建完整性、隐私和账号、声誉和供应链、红队找后门、功效 |
| 对抗性复核 | 12 | 每个“中危”发现，都由 2 名独立复核者尝试推翻或调整严重度 |
| 完整性评审 | 1 | 找遗漏，提出 3 个补缺任务 |
| 补缺调查 | 3 | ① 恶意更新的最坏情况和钉版本的方法；② 发布渠道（旧插件 zip、社交媒体转帖）；③ 带 Cookie 重试循环的触发条件和频率 |

主要手段：
- **逐字节重建**：独立做了约 10 次重建。做法是用 Python 重写 `scripts/build.mjs`，**不运行仓库里的代码**。重建出来的安装文件和发布文件**逐字节一致**；从 2026.9.27.1 起的 7 个发布版本也全部一致。
- **全量阅读**被打包的 15 个源文件；对所有外联方式（fetch / XHR / WebSocket / sendBeacon / Image / script / iframe 等）和混淆特征（eval、new Function、atob、不可见或双向字符、长 base64）逐项搜索。
- **git 和 GitHub API**：查了作者和提交者、签名、分支保护，以及每个 PR 的合并人和评审记录（浅克隆最近 50 个提交，最早到 2026-09-19）。
- **外部条件实测**：13 个 B 站页面的 CSP 响应头；Violentmonkey 源码里的更新默认值；Tampermonkey 的官方文档。
- **没有做的**：没有运行仓库代码；没有下载旧插件 zip；没有登录 B 站做运行时观测。

## 3. 各维度结论

| 维度 | 结论 | 一句话 |
|---|---|---|
| 网络外联 | ✅ 干净 | 只连 api.bilibili.com 和 B 站视频 CDN；没有遥测；诊断信息只写进剪贴板，而且去掉了查询串 |
| 代码执行 / 注入 | ⚠️ 轻微 | 没有 eval，没有远程代码；整个引擎以页面身份运行，并随 main 更新（这是信任问题，不是漏洞） |
| 构建完整性 | ⚠️ 轻微 | 产物和源码一致；但 CI 不校验已提交的发布文件 |
| 隐私 / 账号 | ⚠️ 轻微 | 不碰 Cookie；有一个带 Cookie、没有上限的重试循环（低危） |
| 声誉 / 供应链 | ⚠️ 轻微 | 作者身份前后一致，没有恶意迹象；main 没有保护，至少 2 个账号可写，PR 没有评审记录 |
| 红队 | ⚠️ 轻微 | 没有找到后门；风险集中在以后的更新 |
| 补缺：最坏情况 | ⚠️ 轻微 | 今天是安全的；**只有钉版本、关更新，才能保证以后也安全** |
| 补缺：发布渠道 | ⚠️ 轻微 | 我们看到的社交媒体转帖都只链接到官方仓库；但 Releases 的 “Latest” 仍是已停更的插件 zip |
| 补缺：重试循环 | ⚠️ 轻微 | 确认存在，严重度定为低 |

## 4. 发现清单（复核后的最终严重度）

| # | 发现 | 最终 | 证据 | 说明 |
|---|---|---|---|---|
| S1 | 自动更新指向会变的 `main`：没有分支保护，发布提交没有签名，至少 2 个账号能推送 | **中** | [文件头 L11-12][hdr-upd] · [release.mjs L85][release] · [PR #25][pr25] | 8 份独立复核意见里，6 份认为是“低”，理由是几乎所有用户脚本都这样更新；补缺调查量化最坏情况后维持“中”。本文取“中”，因为影响面是你的 B 站账号。见 §6 |
| S2 | 在 passport / pay / account / member 等子域也会注入（这些页面上它没有任何功能） | 低 | [@match L13][hdr-match] · [L31][frame] · [page-hook L16-17][host-gate] · [native-mse-player L1348-1351][installs] | 现在只是被动地装几个补丁；但如果哪天出了坏版本，它会直接出现在登录、充值和账号页上 |
| S3 | 读不到播放信息时，带 Cookie 的 view / playurl 请求会无上限重试（约每秒 1 次） | 低 | [L1283][gate] · [L1328-1335][catch] · [L1570-1582][tick] | 最初评为“中”，2 位复核者和补缺调查都同意降为“低”。见 §7 |
| S4 | 页面和脚本存储之间的 CustomEvent 通道没有鉴权 | 低 | [loader.js L43-55][bridge] | 同一页面上的任何脚本都能改 BTR 的设置（改完会被重新校验，没有执行代码的途径） |
| S5 | “自定义 CDN”白名单包含整个 `*.akamaized.net` 和 PCDN 厂商的域名 | 低 | [range-core L5][allow] · [L77-84][norm] | 只在“自定义”模式下生效 |
| S6 | 全局补丁会改变 B 站自己记录和上报的内容 | 低 | [native-mse-player L344-370][setitem] | 接管期间不写 5 个解码失败键，吞掉 2 类播放器错误；不读取、也不外传任何值 |
| S7 | CI 不校验已提交的发布文件是否等于源码 | 低 | [userscript-test L20-25][pubtest] | 升级复审时，要看发布文件本身的 diff，不能只看 src/ |
| S8 | 对 CDN 的请求量比原生播放器高很多（自动 8–64 线程，手动最高 128，还有对冲副本） | 低 | [L139-148][ladder] · [L632-635][pushback] | 不带 Cookie，最多触发 IP 级限速；自动模式遇到 412 / 429 会降档，手动模式不会 |
| S9 | 使用旧版的未签名（非 WBI）接口 | 低 | [page-hook L705-758][api] | 只读 GET，参数正常；只是请求特征和官方播放器不同 |
| S10 | 合并的 PR 都没有评审记录；2026-09-27 之前，外部 PR 直接改过发布文件 | 低 | [PR 列表](https://github.com/MrTangLuyao/Bilibili-thread-ripper/pulls?q=is%3Apr) | 那之后，发布文件只由维护者的 release 提交修改 |
| S11 | GitHub Releases 的 “Latest” 仍是已停更的 Chrome 插件 zip（0.9.4.3，没有逐字节核验） | 低 | [Releases][releases] · [README L71][readme-ext] | 作者在 README 里已经要求用户移除旧插件 |
| S12 | BTR 桌面版的发布渠道风险较高 | 中（只针对桌面版） | [桌面版仓库][desk] · [desktop #5][desk5] | 只用浏览器脚本的用户不受影响（2 位复核者对只用脚本的用户都评为“低”；“中”只适用于桌面版）。见 §8 |
| S13 | 页面能探测到它，可以被用来做指纹（`<html>` 上的属性含脚本管理器名称和版本） | 信息 | [loader.js L85-93][loader-start] | 只是只读标记，不是追踪 |
| S14 | 生产代码里留着测试开关 `__BTR_TEST_ALLOW_LIVE__` | 信息 | [live-hook L7][livegate] | 页面几乎不可能及时设置它，影响可以忽略 |
| S15 | 按提交 SHA 安装**并不能**钉住版本：文件头仍指向 `main` | 信息（关键） | [文件头 L11-12][hdr-upd] | 所以安装时必须同时关闭更新检查（[05](05-safe-install.md)） |
| S16 | 实测 13 个 B 站页面都没有强制 CSP（其中 3 个只有 Report-Only） | 信息 | 补缺调查实测的响应头 | 这会放大 S1：坏版本外传数据时，浏览器不会拦 |

## 5. 它会访问什么，不会访问什么

**网络目的地**

| 目的地 | 什么时候 | 带 Cookie 吗 | 内容 |
|---|---|---|---|
| `api.bilibili.com`：`/x/web-interface/view`、`/x/player/playurl`、`/pgc/player/web/v2/playurl` | 页面上没有现成的 DASH 信息时（站内跳转、刷新签名） | 带（和 B 站自己的播放器一样） | 只有 bvid / aid / cid / ep_id；普通的首次打开页面时，一次也不会请求 |
| `*.bilivideo.com` / `.cn` 视频节点（[内置列表][lists]、B 站下发的地址、你自定义的地址） | 播放时 | **不带**（`credentials:'omit'`，Referer 只有源站，[L596-606][cdn-fetch]） | Range GET |
| B 站下发的 `upos-*.akamaized.net` | 海外或自定义模式；大陆模式下只在起播读索引时可能用到 | 不带 | Range GET |
| `<link rel=preconnect>` 到上面这些节点 | 页面加载时 | 不带 | 只建立连接 |
| `raw.githubusercontent.com` | 脚本管理器检查更新、取图标时 | — | 由管理器发起，不是脚本自己的代码 |

**会做的**：读取 `__INITIAL_STATE__` 里的视频字段和 `__playinfo__`；读 localStorage 里它自己的设置、`bilibili_player_codec_prefer_type`（[L1111-1116][codec-pref]）和自动播放偏好；用 GM 存储保存设置；包装 fetch / XHR（[只观察 playurl][wrap]）、history、`Storage.setItem`、`URL.createObjectURL`、`SourceBuffer.buffered`；你点按钮时，把去掉查询串的诊断信息写进剪贴板；直播模块（默认关闭）会屏蔽 B 站的 P2P SDK。

**不会做的**：
- 不读 `document.cookie`，也不碰 SESSDATA、bili_jct、DedeUserID、buvid；
- 没有 POST，没有点赞、投币、关注、评论；
- 没有 `GM_xmlhttpRequest`、`@connect`、`GM_cookie`、`@require`；
- 没有遥测，不连第三方端点；
- 没有 eval，不加载远程代码；
- 不伪造 WBI 签名，不改 UA；
- 不绕过会员、地区或 DRM 限制。

**留下的痕迹**：GM 存储里的 `sync`；各子域 localStorage 里的 `BTR_Userscript.sync`、`BTR_Userscript.local`、`BTR.codecFailuresCleared`；`<html data-btr-userscript …>` 等属性；`window.__biliThreadRipperDebug` 等全局变量。

## 6. 主要风险：不钉版本时的静默自动更新

**谁能发版**：仓库所有者，外加至少 1 名有推送权限的协作者（见 [PR #25][pr25] 的合并记录：在本地合并，提交没有签名）。`main` 分支 `protected:false`，rulesets 为空；HEAD 和各发布提交没有签名（只有个别网页端合并提交带 GitHub 自动签名），发布标签是轻量标签。发版脚本自己就写着，推送到 main 就等于发给所有用户（[release.mjs L85][release]）。

**新版本多快到你这里**：raw.githubusercontent 缓存 5 分钟，加上脚本管理器每天检查一次，大约 1 天内就会到。
- **Violentmonkey**（BTR 推荐的管理器）默认每天检查一次，而且 `notifyUpdates:false`。连文件头（`@match`、`@grant`）的变化也会静默应用（[源码][vm-defaults]）。
- **Tampermonkey**：据维护者在 GitHub issue 里的说明，只有 include / match / exclude、connect 或更新地址变化时才会弹出确认页；只改代码时会静默安装（我们没有在当前版本里复核）。官方文档确认，`@downloadURL none` 可以关闭更新检查（[文档][tm-dl]）；不过在 Tampermonkey 5.5.1 上实测，改成 `none` 后它内部仍保留原来的下载地址，所以安装指南要求同时关掉脚本的「检查更新」（见 [05 ③B](05-safe-install.md)）。

**如果出现一个坏版本，在文件头不变的情况下它能做什么**（这是推演，没有实际攻击验证）：
1. **以你的身份在网页里操作**：页面代码能读到非 HttpOnly 的 `bili_jct`（B 站自己的播放器就靠它填 `csrf`），可以发评论、发弹幕、发私信、关注、点赞投币、改资料、删内容，也能读你的历史、收藏和私信。能不能直接付款，**没有测试**。
2. **外传数据**：13 个页面都没有强制 CSP，`fetch`、`sendBeacon`、`new Image()` 都能把数据发到任意服务器。
3. **延迟的会话劫持**：SESSDATA 是 HttpOnly，读不到。但社区整理的 API 文档显示，登录接口返回的 JSON 里带有会话信息（[来源][apicollect]）。BTR 已经包装了页面的 fetch / XHR（目前只过滤 playurl），坏版本只要放宽过滤，就可能在你**下次登录时**截获会话。在 passport 页面上，它还能记录你输入的密码和验证码。
4. **如果连文件头也改了**：Violentmonkey 会静默接受 `@match` 扩大到所有网站。Tampermonkey 文档写明，**BETA 版**的 `GM_cookie` 可以读取 httpOnly Cookie（[文档][tm-cookie]）。所以除非确实需要，不要用 Tampermonkey BETA。

**可能性和影响**：可能性低。作者身份公开且前后一致，星标增长和[作者的介绍视频][promo]发布时间吻合（[Trendshift][trend]），没有任何恶意迹象。但影响高，涉及你的 B 站账号。

**对策**：钉死提交、关闭更新检查、排除敏感子域，升级前先复审 diff。具体方法见 [05 · 安全安装](05-safe-install.md)。

## 7. 带 Cookie 的重试循环（低危 bug）

- **机制**：BTR 自己读取播放信息失败时，[catch 分支][catch] 只安排重试，不标记失败；[1 秒定时器][tick] 又会直接调用 `startPlayer`；而[唯一能让它停手的标记][gate]（`failedRoute`）在这条失败路径上从来不会被设置。[`recordTakeoverFailure`][fail] 只决定要不要显示错误，既没有上限，也不退避。
- **频率**：前台标签页每分钟约 60 次尝试。第一个请求就失败时，每分钟约 60 个带 Cookie 的请求；view 成功、playurl 失败时，每分钟约 120 个。后台标签页 5 分钟后会被 Chrome 节流到每分钟约 1 次（[Chrome 定时器节流][throttle]）。开多个标签页就成倍增加。
- **触发条件**（必须同时满足）：
  - 页面上有一个宽于 200px 的播放器 `<video>`；
  - 没有缓存的 DASH 信息；
  - BTR 自己的请求失败了；
  - B 站自己的 playurl 也拿不到 DASH。

  现实中，这就是**你本来就看不了的视频**（地区限制、充电专属），或者**你的 IP 已经被风控（412）**。正常打开视频页时，额外请求是 0 次；站内跳转时是 1 次 view 加 1 次 playurl，B 站自己的响应一到就取消。
- **默认不提示**：「显示错误」默认是关的（[runtime-notices L36-38][errnotice]）。
- **后果**：最可能的是让 IP 级的临时 412 持续更久。账号级处罚目前没有任何报告（这一点是推测）。
- **对策**：打开 BTR 设置里的「显示错误」；遇到地区限制、打不开或要验证码的视频，**关掉那个标签页，或者临时关掉 BTR**。
- **给上游的建议修法**：失败 N 次后设置 `failedRoute`，或者加入指数退避。

## 8. 桌面版和旧 Chrome 插件：请谨慎

- **BTR 桌面版**（[仓库][desk]，会修改官方 Windows 客户端）：
  - 用 `irm … | iex` 安装；EXE 没有签名，没有 CI，打包好的 zip 直接提交在仓库里；
  - 需要 UAC 提权，而提权步骤会执行用户可写目录 `%LOCALAPPDATA%` 里的 JS；
  - 会写入 HKCU 开机自启；更新只靠同一个仓库里的 SHA-256 校验；
  - 维护者在 [desktop #5][desk5] 里建议“暂时关闭智能应用控制”。如果你已经关了，Windows 2026-04 的更新之后可以不重装系统、直接重新打开（[来源][sac]）。

  在浏览器里看 B 站的话，用不到桌面版。
- **旧 Chrome 插件 zip / .crx**（[Releases][releases] 的 “Latest” 仍是 0.9.4.3）：已经停更，不会自动更新，我们也没有逐字节核验；作者在 [README L71][readme-ext] 里要求用户移除它。如果你以前用开发者模式装过“Bilibili 线程撕裂者”插件，请到 `chrome://extensions` 里移除，**不要和脚本版同时开**。
- **非官方渠道**：BTR 没有上架 Greasy Fork 或任何商店（[#24][i24]），唯一的官方渠道是 GitHub。同名的 fork 和移植都不是官方的。

## 9. 声誉与社区信号

- 作者的 GitHub 账号从 2020 年就有了；作者在 GitHub 和 B 站上的身份公开，而且前后一致（比如作者自己发布的[介绍视频][promo]）。没有找到捐赠或变现链接。
- 星标曲线和 2026-09-16 发布的介绍视频时间吻合（[Trendshift][trend]），不像刷星。
- 审计时累计提交的 26 个 issue（含已关闭的）都是功能问题；没有看到盗号、封号或风控的报告。但项目创建于 2026-08-27，广泛使用只有约 4 周（自 2026-09-16 的介绍视频起），这只是弱证据。

## 10. 审计局限

- **只覆盖 `0302b34`**，之后的任何提交都需要重新审计。
- 纯静态审计：没有在真实页面里观测请求频率；重试循环的频率来自对控制流的推演。
- 浅克隆，2026-09-19 以前的历史没有看；协作者权限和分支保护的细节，只能看到公开信号。
- Tampermonkey 当前版本的更新弹窗行为、地区限制页面会不会渲染 `<video>`、付款是否需要额外确认：都没有验证。
- 旧插件 zip 没有下载核验。
- 替代方案（MBGTEB、realzza 等）只做了事实核查和关键字扫描，没有做同等深度的审计。

---

上一篇：[02 · 原因与实测](02-why-cdn.md) · 下一篇：[04 · 替代方案](04-alternatives.md)

<!-- 链接（BTR 源码均固定在提交 0302b34） -->
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
