# 05 · 安全安装 BTR：钉版本、关更新、排除敏感子域

**简体中文** · [English](../en/05-safe-install.md) · [← 返回首页](../../README.md)

> **先确认你真的需要它**：先做完首页的 [60 秒自查清单](../../README.md#60-秒自查清单)（尤其是硬件加速），再用 [`cdn-bench.js`](../../tools/cdn-bench.js) 确认冷门视频确实卡在 CDN 上（[02 §8](02-why-cdn.md#8-自己测一次)）。如果单连接换个节点就够，轻量的 realzza 可能更省心（§6.1）。
>
> 本页的配方只针对已审计的提交 `0302b34`（v2026.10.8.1）。界面文字后面标有：
> - **【文档已核实】**：对照过官方文档或源码；
> - **【界面未核实】**：按经验写的，实际文字可能略有不同。

```
准备（§1）→ 钉版本安装（§2 Tampermonkey 或 §3 Violentmonkey）→ 验证 → 首次设置 → A/B 测试（§5）
         → 达标：日常使用（§7）；不达标：替代方案（§6）
```

## 1. 准备

1. **浏览器最新、硬件加速打开**（[01](01-diagnosis.md)）。
2. **只用一个脚本管理器**，Tampermonkey 正式版或 Violentmonkey 二选一：
   - 同一个脚本装在两个管理器里，会被注入两次。
   - 除非确实需要，**不要用 Tampermonkey BETA**：官方文档写明，`GM_cookie` 读取 httpOnly Cookie（比如登录会话）这项功能只在 BETA 版支持（[文档][tm-cookie]）。
   - 确认扩展是官方版本：`chrome://extensions` → 详情，地址栏里的 ID 应该是 Tampermonkey 正式版 `dhdgffkkebhmkfjojejmpbldmpobfkfo`（[TM FAQ Q406][q406]）。
3. **打开「允许运行用户脚本」**：`chrome://extensions` → 你的脚本管理器 → 详情。Chrome 138 起必须打开（[TM FAQ Q209][q209]）。
4. **停用其它 B 站加速脚本或扩展**（realzza、MBGTEB、CDN 切换器、旧的 BTR 插件版等）。
5. **先测基线**：用 [`cdn-bench.js`](../../tools/cdn-bench.js) 测 1 个热门视频和 1 个**没看过**的冷门视频（登录，用平时的清晰度），把结果保存下来。

## 2. 安装配方：Tampermonkey（Chrome / Edge）

**① 打开钉在提交上的安装地址**。不要用 README 里指向 `main` 的按钮。

```
https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/0302b345cdfe367ac599b52dc6874e3f7967e220/user_scripts/bilibili-thread-ripper.user.js
```

这个地址按提交哈希定位，内容不会再变，就是审计过的那份文件（blob `0dd5d9c`）。Tampermonkey 会弹出安装页。

> 想再确认一层：把这个地址的文件另存下来，计算 SHA-256。Windows 用 `certutil -hashfile 文件名 SHA256`，macOS / Linux 用 `shasum -a 256 文件名`。结果应为 `7766622730f6d24febb89cd3669ff0c384997c260c652668082d84af61724dd9`（405,714 字节，LF 换行）。

**② 在安装页上核对**，全部相符再点「安装」【界面未核实】：

- 名称是 `Bilibili 线程撕裂者`，版本是 **`2026.10.8.1`**。
- 匹配范围只有 `https://*.bilibili.com/*`。
- 权限**正好 6 项**：`GM_registerMenuCommand`、`GM_addElement`、`unsafeWindow`、`GM.getValue`、`GM.setValue`、`GM_addValueChangeListener`。
- **没有** `@require`、`@resource`、`@connect`、`GM_xmlhttpRequest`、`GM_cookie`。
- `@updateURL` / `@downloadURL` 指向 `…/main/…`：这是预期的，下一步会关掉。
- 还会看到 `@run-at document-start`、`@sandbox JavaScript`、`@inject-into content`、一个指向 main 的 `@icon`，以及 `@namespace`、`@homepageURL`、`@supportURL` 等说明字段，这些也是预期的。前三项只决定脚本什么时候、注入到哪个执行环境，不是额外的权限；图标只是一张图片。

**有任何一项不符，就不要安装。**

**③ 关掉这个脚本的自动更新**。A、B 都要做，C 是额外的保险：

- **A【文档已核实】** 管理面板 → 点「Bilibili 线程撕裂者」打开编辑器，把文件头里 `@updateURL`、`@downloadURL` 这两行（第 11–12 行）改成下面这样，然后保存（Ctrl+S）。官方文档说明，`@downloadURL` 设为 `none` 时不做更新检查（[文档][tm-dl]）。

  ```
  // @updateURL    none
  // @downloadURL  none
  ```

- **B【必做；界面未核实】** 打开这个脚本的「设置」标签页，取消勾选「检查更新」（Check for updates），保存。
  > 为什么 A 不够：2026-10-13 在 Tampermonkey 5.5.1 上实测，只做 A 之后，Tampermonkey 内部记录的 `updateURL` 变成了 `none`，但 `downloadURL` 仍然保留安装时的 `…/main/…` 地址，「检查更新」也仍是勾选状态。与其依赖 Tampermonkey 对 `none` 的解释，不如把这个开关也关掉。
- **C【设置项由维护者确认，位置未核实】** Tampermonkey 设置 → 配置模式切到「高级」→「脚本更新」→ 检查间隔设为「从不」（[issue #1753][tm1753]）。**注意：这一项会影响所有脚本。**

**④ 排除敏感子域**【文档已核实：`@exclude` 优先于 `@match`（[文档][tm-ex]）；用户排除见 [FAQ Q103][q103]】。二选一：

- 在 ③A 的同一次编辑里，在 `@match` 那行下面加上：

  ```
  // @exclude      https://passport.bilibili.com/*
  // @exclude      https://pay.bilibili.com/*
  // @exclude      https://account.bilibili.com/*
  // @exclude      https://member.bilibili.com/*
  ```

- 或者在脚本的「设置」→「用户排除」（User excludes）里逐条添加这 4 个地址。

> ⚠️ 粘贴时注意换行：每条 `// @…` 必须单独占一行。如果整块复制粘贴，最后一行末尾没有换行，它会和下一行 `// @run-at       document-start` 粘成一行——实测踩过这个坑：结果 `@run-at document-start` 失效，最后一条排除规则也坏了。保存前看一眼 `// @run-at` 是否仍然独占一行。

BTR 在这些子域上本来就没有任何功能，排除之后，坏版本也碰不到登录、充值和账号页。www、m、live、space 要保留，看视频要用。注意 www 页面里也有登录弹窗，所以排除只是**缩小**风险，钉版本才是关键。

**⑤ 验证**。今天 `main` 和钉死的版本是同一份文件，所以“检查更新时没有新版本”什么也证明不了，要按下面逐项看：

- 关掉再重新打开管理面板，打开脚本编辑器，确认第 11–12 行仍然是 `none`（说明保存生效了）。
- 「检查更新」处于未勾选状态（③B）。
- 编辑器里 `// @run-at       document-start` 仍然独占一行，4 条 `@exclude` 各占一行。
- 管理面板里显示的版本是 `2026.10.8.1`。
- 打开任意一个视频：页面上有 BTR 的悬浮球；右键「视频统计信息」里，Player Type 显示 `BTR Native`。
- 打开 `https://passport.bilibili.com/login`，在 F12 控制台输入 `document.documentElement.hasAttribute('data-btr-userscript')`，结果应该是 `false`，说明排除生效了。

**⑥ 首次设置**：

- 播放策略**明确**选 HEVC（或者在 GPU 支持 AV1 硬解时选 AV1），不要留在「默认」。BTR 会跟随这个设置（[源码][btr-codec]）；选「默认」时，它按 AV1 > HEVC > AVC 的顺序，只用 `isTypeSupported` 判断（[源码][btr-order]），而这在没有 AV1 硬解的电脑上可能落到 CPU 软解。
- 在 BTR 设置面板里打开「显示错误」，让接管失败（包括重试循环，见 [03 §7](03-btr-security-audit.md#7-带-cookie-的重试循环低危-bug)）不再静默发生。
- 「直播加速（实验性）」保持关闭。其余先用默认值（大陆节点、自动线程数、全接管），然后进入 §5。

**⑦ 记一笔**：安装日期、来源（提交 `0302b34`）、版本号。

## 3. 安装配方：Violentmonkey

适合更信任 BTR 推荐的 Violentmonkey 的人，或者用 NVIDIA RTX 视频超分（VSR）的人：有一位用户报告，BTR 在 Tampermonkey 下会让 VSR 失效，在 Violentmonkey 下正常（[#46][b46]，未修复）。**这是替换，不是新增**，同一时间只开一个管理器。下面的界面文字取自 Violentmonkey 源码里的中文语言文件；它的更新行为（默认每天检查、**静默**更新）也来自源码。

1. 停用其它脚本管理器，安装 Violentmonkey；在 `chrome://extensions` → Violentmonkey → 详情里，打开「允许运行用户脚本」。
2. 打开 §2 ① 的钉提交地址进行安装；核对版本 2026.10.8.1、匹配范围和 6 项权限（同 §2 ②）。
3. 管理面板 → BTR → 编辑 →「设置」标签：
   - 取消勾选「允许更新」；
   - 把「检查更新地址：」和「下载更新地址：」都填成钉提交地址，这样即使手动点了更新，拿到的也是同一份文件；
   - 在「@exclude-match 规则」里加上 §2 ④ 的 4 个地址。

   保存。
4. 验证：重新打开脚本的「设置」，确认「允许更新」没有勾选、两个更新地址都是钉提交地址；版本是 2026.10.8.1；passport 页面上 `data-btr-userscript` 为 `false`。
5. 首次设置同 §2 ⑥。

## 4. 以后怎么安全升级

1. **不追新**：只在需要某个修复时才升级。新版本发布后，至少等一周，看看 [issues][issues] 里有没有问题报告。
2. 在[发布文件的提交历史][hist]里找到新的 release 提交，复制**完整**哈希，下面记作 `<NEW>`。
3. 打开 `https://github.com/MrTangLuyao/Bilibili-thread-ripper/compare/0302b345cdfe367ac599b52dc6874e3f7967e220...<NEW>`，**重点看发布文件 `user_scripts/bilibili-thread-ripper.user.js` 本身的改动**。CI 不校验它是否等于 src/，见 [03](03-btr-security-audit.md) S7。
4. 在 diff 里用 Ctrl+F 逐项搜索：
   - **文件头**：`@match`、`@include`、`@exclude`、`@grant`、`@connect`、`@require`、`@resource`、`@updateURL`、`@downloadURL`、`@run-at`
   - **账号相关**：`document.cookie`、`cookieStore`、`bili_jct`、`SESSDATA`、`DedeUserID`、`csrf`、`passport`、`login`、`POST`，以及新增的 `credentials: "include"`
   - **外传或执行**：`sendBeacon`、`WebSocket`、`EventSource`、`new Image`、`eval`、`new Function`、`atob`、`import(`、`Worker`、`innerHTML`、`GM_xmlhttpRequest`、`GM_cookie`、`GM_download`
   - **新域名**：任何不属于 bilibili.com / bilivideo.* / hdslb.com / akamaized.net / github 的 `https://` 字面量；大段 base64、成串的 `\x` / `\u` 转义、整行压缩的代码
5. 看不懂或者觉得可疑：先别升级。可以请懂代码的朋友帮忙复审，或者借助 AI 代码审查工具，做一遍重建比对、关键字扫描和 diff 阅读。
6. 通过以后：打开 `https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/<NEW>/user_scripts/bilibili-thread-ripper.user.js` 覆盖安装，然后**重做 §2 的 ②–⑤**（Violentmonkey 是 §3 的 2–4），因为新文件又会指向 main，也没有排除规则。

## 5. A/B 测试：找到最适合你的设置

**固定条件**：同一个浏览器窗口；笔记本插电；VPN / WARP / 代理关闭；只开 BTR 这一个加速器；清晰度用你平时看的那档（最好 1080P 以上）；播放策略固定；测量时关弹幕。

**视频**：H 是一个热门视频；C1…C6 是六个**不同的**冷门视频，因为冷门视频测一次就“热”了。也可以用同一个很长的冷门视频，每轮跳到一个**从没播过**的位置（比如 10、20、30、40 分钟处）。

**每轮的流程**（约 4 分钟）：

1. 在播放器里关掉「自动开播」，按 F5 刷新。
2. 粘贴 [`play-monitor.js`](../../tools/play-monitor.js)，然后点播放。
3. 看 3 分钟，中途拖动 2 次，都拖到没看过的位置。
4. 在控制台输入 `__pm.stop()`。

同时留意「视频统计信息」里的 Video Speed 和 Video DataRate，以及 BTR 面板里的「目前总线程」。

| 轮次 | BTR 设置 | 视频 |
|---|---|---|
| V0 基线 | BTR 关闭（悬浮球面板里的总开关） | C1 + H |
| V1 | 大陆 + 自动线程数 + 全接管（默认） | C2 + H |
| V2 | 海外 + 自动线程数 + 全接管 | C3 + H |
| V3 | 自定义：勾选 cdn-bench 冷门测速里最快的 4–6 个节点，尽量分属不同厂商（hw 和 08c 都是华为，共用一组 IP），比如 ali、hw、cos、bd，再加上自动线程数 | C4 + H |
| V4 | V1–V3 里最好的那一组，改用「兼容模式」 | C5 + H |
| V5（可选） | 最好的那一组，播放策略在 HEVC 和 AV1 之间切换 | C6 + H |

- 线程数保持「自动」。只有出现 412 / 429 报错或 CPU 占用很高时，再试固定 16。
- 自定义节点只填 `*.bilivideo.com`。
- 想让热门视频继续走 B 站分配的 Akamai（未验证）：在 V3 里「手动添加」**你的**分配主节点主机名（cdn-bench 表里“分配·主”那一行），其它 akamaized.net 一律不要填。据源码推断（[cdn-resolver.js][btr-custom]），有些地址被 Akamai 拒绝（403）后会被停用（[停用规则][btr-ban]），这是预期的，也无害。

**通过标准**（每轮都看）

| 指标 | 通过 | 怎么看 |
|---|---|---|
| 冷门视频的下载速度 | 3 分钟内 Video Speed 持续 ≥ **1.5 倍** Video DataRate | 视频统计信息 |
| 卡顿（不含拖动） | **0 次**（1 次算勉强，2 次及以上不通过） | play-monitor |
| 拖动后的等待 | 每次 ≤ 3 秒 | play-monitor |
| 首帧时间 | 热门：比 V0 慢不超过 1.5 秒；冷门：不比 V0 慢 | play-monitor |
| 丢帧率 | < 1% | play-monitor / 视频统计信息 |
| 没有新问题 | 清晰度切换、弹幕、自动连播、分 P、合集、循环、倍速、全屏、快捷键、HDR / 杜比（如有）、RTX VSR（如用）都正常 | 手动检查 |
| 热门视频不退步 | 0 卡顿，起播不明显变慢 | play-monitor |

**怎么选**：在全部通过的设置里，挑副作用最少的一组；两组差不多时，优先「兼容模式」和更少的自定义节点。如果 **V0 本身就通过了**，说明你暂时不需要 BTR，按 §7 卸载即可。

**记录表**

| 轮次 | 视频 | 清晰度 / 编码 | Video Speed ÷ DataRate | 卡顿次数 / 总秒数 | 拖动等待 | 首帧 ms | 丢帧率 | 新问题 | 通过？ |
|---|---|---|---|---|---|---|---|---|---|
| V0 | C1 | | | | | | | | |
| V0 | H | | | | | | | | |
| V1 | C2 | | | | | | | | |
| V2 | C3 | | | | | | | | |
| V3 | C4 | | | | | | | | |
| V4 | C5 | | | | | | | | |
| V5 | C6 | | | | | | | | |

## 6. 不达标时的替代方案（按顺序）

完整对比见 [04 · 替代方案](04-alternatives.md)。**任何时候都只开一个加速器。**

### 6.1 realzza Bilibili Accelerator（单连接换源，权限最低）

适合两种情况：cdn-bench 显示换个节点单连接就够；或者 BTR 的接管影响了你要用的功能。

- 先停用或删除 BTR。
- 安装：认准 [Greasy Fork #582026][rzgf]（作者 realzza；#588296 是另一个同名的脚本），或者 GitHub 的 [v0.5.0][rzrel]。核对 `@grant none`，版本 0.5.0。
- 同样按 §2 ③A 和 ③B：把 `@updateURL`、`@downloadURL` 改成 `none`，并取消勾选「检查更新」；再加上 §2 ④ 的 4 条 `@exclude`，因为它的匹配范围也包含 passport 等子域。
- 预期：热门视频留在原节点；冷门视频的提升取决于它的候选池（没有 08c）。我们只做了核查（不访问 Cookie、不连第三方端点、发布文件就是源码拼接），没有做完整审计。

### 6.2 MBGTEB 1.9.0，只开 Thread Ripper

适合 BTR 的全接管和兼容模式都有你接受不了的问题时。

- 先停用 BTR 或 realzza。
- 从钉了版本号的地址安装（npm 上同一个版本号的内容不能再改）：

  ```
  https://unpkg.com/make-bilibili-great-than-ever-before@1.9.0/dist/make-bilibili-great-than-ever-before.user.js
  ```

  然后同样按 §2 ③A 和 ③B 关掉更新。
- 在脚本管理器的菜单里**打开** Thread Ripper（默认关闭），**关掉**其它会改变行为的模块，至少包括：伪装 UA 的“强制 4K”、禁用 AV1（如果你能硬解 AV1）、包装 localStorage 的模块（菜单名称未核实）。
- 风险：这个模块合并时间很短，是作者自己合并的，没有公开测速数据，我们也没有审计过。同样按 §5 做 A/B 测试。

### 6.3 离线：第三方下载器或官方客户端

- **[Bili23-Downloader][b23] ≥ 2.20.0**：离线下载冷门视频最快。地区要**手动**设为 CN，把 ali / hw 排到最前，线程调到 8–10。⚠️ 它把 SESSDATA **明文**存在 AppData 下的 config.json，不用的时候请在软件里退出登录。仅限个人离线观看。
- **官方客户端的离线缓存**：最稳，零新增风险，但不会更快。冷门视频要提前缓存。

### 6.4 进阶（未验证）：只让视频域名走港 / 日中转

只在你**已经有**可信的港 / 日直连节点时才考虑。要点：

- www.bilibili.com、api.bilibili.com 保持 DIRECT；
- 让 `DOMAIN-SUFFIX,bilivideo.com`、`DOMAIN-SUFFIX,bilivideo.cn` 和你的 Akamai 分配主节点的**精确主机名**，都指向规则组 `[DIRECT, HK, JP]`，按视频手动切换（热门视频用 DIRECT）；
- **永远不要**写 `DOMAIN-SUFFIX,akamaized.net`；
- 规则地址钉到具体提交；
- 代理客户端用最新版。

详见 [04 §C](04-alternatives.md#c-网络层)。

## 7. 日常使用与卸载

**日常**

- **永远只开一个加速器。**
- **不点更新**：BTR 保持钉版本，升级前按 §4 复审。
- **遇到看不了的视频**（地区限制、充电专属、出现 412 或验证码）：关掉那个标签页，或者用悬浮球面板的总开关临时关掉 BTR，避开带 Cookie 的重试循环（[03 §7](03-btr-security-audit.md#7-带-cookie-的重试循环低危-bug)）。
- **不要公开完整的 `.m4s` 地址**：里面有 `mid`（你的 UID）和 `oi`（你的 IP）。cdn-bench 的结果和 BTR 的「复制诊断信息」都不含这些。
- **每季度看一眼**：BTR 的 issues 里有没有“风控”或“封号”的报告；浏览器和脚本管理器是不是最新版；硬件加速是不是还开着（浏览器重置或驱动更新后可能被关掉）。

**干净卸载 BTR**

1. 脚本管理器的管理面板 → BTR → 删除（如果有回收站，也一并清掉）。
2. 可选：F12 → Application → Local Storage → `https://www.bilibili.com`（以及 m、live），删掉 `BTR` 开头的键（`BTR_Userscript.sync`、`BTR_Userscript.local`、`BTR.codecFailuresCleared`）。留着也无害。
3. 需要的话，把播放策略改回原来的设置。
4. 如果以前装过旧的 Chrome 插件版（用开发者模式加载的“Bilibili 线程撕裂者”），到 `chrome://extensions` 里移除。
5. 打开一个视频，确认「视频统计信息」里的 Player Type 回到了 `DashPlayer`。

---

上一篇：[04 · 替代方案](04-alternatives.md) · [返回首页](../../README.md)

<!-- 链接 -->
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
