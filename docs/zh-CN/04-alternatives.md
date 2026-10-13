# 04 · 替代方案对比

**简体中文** · [English](../en/04-alternatives.md) · [← 返回首页](../../README.md)

> 调研日期：2026-10-13。一共调研了 5 个方向（浏览器内、客户端、社区经验、网络层、解码），每个方向都配了一名独立的事实核查员。**表格已经按核查员的更正改写过**，两者冲突时以核查结论为准。星标、安装量和日期都是当天的数据，之后会变。
>
> 除了 BTR（见 [03](03-btr-security-audit.md)）以外，这里的方案**只做了事实核查和关键字扫描，没有做同等深度的审计**。下面写的问题，都是我们在某个时间点观察到的现象或代码行为，附有来源，不是对作者的评价。感谢这些项目的作者把代码公开出来。

**图例**（对“海外看冷门视频卡”这个问题）：✅ 对症　⚠️ 部分有用　❌ 不对症　❓ 未经验证

**先回顾一下瓶颈**（[02](02-why-cdn.md)）：冷门视频在海外边缘（Akamai / cosov / aliov）上回源很慢；“大陆节点 + 并行”稳定在 24–26 Mbps。热门视频本来就不卡。另外，**本地硬件加速的问题要先排除**（[01](01-diagnosis.md)），哪个脚本都修不了它。

## A. 浏览器里（脚本 / 扩展）

| # | 方案 | ⭐ / 安装量 | 最近活动 | 机制 | 是否对症 | 风险 | 结论 |
|---|---|---|---|---|---|---|---|
| 1 | [BTR][btr]，钉在 `0302b34` | 1.2k★ | 2026-10-10 | 全接管（自己喂 MSE）或兼容模式；大陆 / 海外 / 自定义节点；自动 8–64 线程；对冲重试；预读 45 秒 | ✅ 正好对应“大陆 + 并行”。但大陆模式会弃用 B 站给的 Akamai，热门视频起播可能慢一点 | 不钉版本：自动更新（中）；钉版本后：低。全接管历史上回归较多（[#28][b28]、[#46][b46] 仍未关闭） | **首选**（已审计，[03](03-btr-security-audit.md)） |
| 2 | [MBGTEB][mbg] 1.9.0 的 Thread Ripper 模块（作者 SukkaW） | 727★ | 2026-10-10 合并 | 只改 XHR / fetch，不接管播放器；每个视频都实测所有镜像（含 Akamai）；每个主机最多 6 个、总共最多 32 个并发；不同主机返回的重叠字节会互相比对 | ✅ 设计对路，侵入更小；@match 只有 www / t / live / space | 这个模块是作者自己合并的，0 评审，还没有公开测速数据（[PR #31][mbg31]）；**其它约 15 个模块默认全开**（伪装 macOS Safari UA、禁用 AV1、包装 localStorage、屏蔽遥测等）；从 unpkg `@latest` 自动更新（npm 发布带 SLSA 来源证明，这一点降低了风险） | **备选**；等有了实际使用反馈再评估 |
| 3 | [realzza Bilibili Accelerator][rz] v0.5.0 | 602★ · [Greasy Fork #582026][rzgf] 约 4.7k 安装 | 2026-09-28 | 先用 B 站分配的节点；如果测出来跟不上码率（或 1 秒内没有首字节），就让 2 个候选节点竞速，快 1.5 倍以上才切换；**单连接** | ⚠️ 热门视频留在原节点（好）；冷门视频的提升取决于候选池里有没有够快的节点。候选池固定为 cosov、aliov、hwov、ali、tf-all-hw、hw、cos、tf-all-tx，**没有 08c**；荷兰案例里 ali、hw 单连接 4–7 Mbps | 权限最低（`@grant none`，不连第三方端点，发布文件就是源码拼接；Greasy Fork 版和 GitHub 版逐字节一致，只差更新地址两行）；但 @match 包含 passport 等所有子域；Greasy Fork 会自动更新；作者公开了美国西岸的测量数据（[vod-routing.md][rzdoc]） | **轻量选择**（cdn-bench 显示单连接就够时） |
| 4 | [Bilibili Video CDN Switcher][gf500]（Greasy Fork #500213） | 约 13.7k 安装 | 2026-08-25 | 把播放地址换成一个固定主机 | ⚠️ 没有选择界面，要换主机得改源码里的 `CustomCDN` 变量；默认只改主地址，主地址是 Akamai 时还要另外打开「替换备用播放地址」；固定一个大陆主机会拖慢热门视频 | 没有许可证（“Free For Personal Use”）；还会替换页面的 XHR 和 fetch | 只适合临时诊断 |
| 5 | [Overseas Video Speedup][ovs]（海外视频加速） | 16★；第三方统计约 5k 用户（可能过时） | 2026-10-12 | 300 个节点，按国家预设，可选自动切换 | ❌ 预设只覆盖 TW / SG / HK / JP / AU / US，其它国家（比如欧洲各国）会退回台湾预设；装上就开始改写分段地址，不先测速；单连接 | 提交 bug 报告时，诊断信息（IP、运营商、省份、最近 10 分钟看过的视频 ID）会发到开发者的私有仓库（只在你主动提交时发生，见其 PRIVACY.md）；配套的 CDNSpeedTest.exe 见 §F；AMO 上标的 MPL-2.0 和仓库里的自定义许可不一致 | 不推荐 |
| 6 | [CCB][ccb]（Custom CDN of Bilibili） | 220★ · Greasy Fork 约 4.1k | 代码 2026-08-07 | 从作者的 GitHub Pages 拉节点列表，手动钉一个节点 | ❌ [#15][ccb15]（未关闭）：默认节点是 Akamai / cosov 时换不掉，而这正是荷兰案例的分配情况；2026-09 有“失效”反馈 | 使用 `GM_xmlhttpRequest`，远程列表只校验格式；会向 Web Worker 注入代码；README 说明代码由 AI 编写 | 不推荐 |
| 7 | [Bili Turbo][turbo] | 0★ | 2026-10-10（只有一个提交） | 对 hw / 08c / ali / cos 发 4 路并行 | ❌ 从代码看，站内跳转后 Akamai 到 bilivideo 的映射会失效，变成 4 路都打 Akamai（冷数据最差的情况） | 没有许可证；会把 HTTP 200 当成 Range 结果接收（可能写入错误数据）；解压后手动加载，不会更新 | 不推荐 |
| 8 | 其它小众项目：[BiliLoader][bl]（预热海外边缘，在欧洲太慢）、[Bili Pilot][pilot]（只用 B 站给的地址）、[liiliiliil][lii]（不处理 akamaized.net）、[zk39][zk39]（停更）、[BiliKit][bkit]（固定大陆节点）、[SanJerry007][sj]（偏好 Akamai）、[stabruriss][stab]（只有海外线路）、PCDN 屏蔽器（海外通常分配不到 PCDN） | — | — | — | ❌ | — | 不推荐 |
| 9 | BTR 的各个 fork、[BiliThrottle][thr]（BTR 改包） | 0–2★ | — | 同 BTR | — | 都落后于上游；改包没有审计 | 不推荐 |

## B. 客户端与下载器（Windows）

| # | 方案 | ⭐ | 最近活动 | 机制 | 是否对症 | 风险 | 结论 |
|---|---|---|---|---|---|---|---|
| 1 | 官方客户端 + 离线缓存 | 闭源 | — | 播放和网页一样是单连接（没有完全验证） | ⚠️ 在线播放不会更快；适合“先缓存再看” | 第一方登录，不增加任何泄露面；缓存文件只能在客户端里播放 | 离线首选（零新增风险） |
| 2 | [Bili23-Downloader][b23] v2.20.0 | 8.3k★ | 2026-09-27 | 去掉 PCDN，按可编辑的列表换主机，每个文件 4 线程（最多 10） | ✅ 离线下载冷门视频很快。但**必须**手动把地区设为 CN、把 ali / hw 排到前面、线程调到 8–10，否则海外出口会被自动判成海外列表（aliov、cosov） | SESSDATA 以**明文**存在 AppData 下的 config.json；2.15 版曾被杀毒软件误报；据 CI 配置和发布说明，2.20 起做了代码签名；此前已有下载器在收到律师函后停止维护的先例 | 离线首选（第三方） |
| 3 | [PiliPlus][pili] 2.1.6.x | 19.4k★ | 2026-10-12 | mpv 播放；21 个可选 CDN；播放器内可以对**当前视频**测速 | ⚠️ 单连接；换主机时从 Akamai 签名地址出发，可能返回 403（[#3242][pili3242]）；冷门 4K 不够用 | 不登录也能看 1080P（无痕 / 游客模式，不用交出 SESSDATA）；登录后令牌不加密保存；Windows 包没有签名；有一个 Windows 画面冻结问题（#2700）；它的前身 PiliPala 收到过侵权通知 | 可以试（1080P） |
| 4 | [lemonteaau/PiliPlus][lemon]（BTR 移植版） | 9★ | 2026-10-12 | 本机 127.0.0.1 Range 代理 + BTR 核心 | ❓ 设计对路，但还没有真实网络验证；默认开着“海外节点” | 个人 AI 辅助的分叉；每天自动合并上游并发布，没有评审；没有签名 | 实验性 |
| 5 | [BBDown][bbd] 1.6.3 | 13.9k★ | 2026-05-14 已归档 | `--upos-host` + 多线程 | ⚠️ 能下，但已经不再维护 | 默认 `--force-http`，每个媒体请求都带 Cookie，登录后 SESSDATA 会**明文**传输；`serve` 模式是无鉴权、允许任意来源的 API，网页可以利用它让本机运行任意程序 | 只在未登录、并加 `--force-http false` 时用；**永远不要用 `serve`** |
| 6 | yutto、yt-dlp、Gopeed 扩展、bilibili-tui、mpv + cdn-router | — | 活跃 | 只能用 B 站给的地址，或者单连接 | ❌ | yt-dlp 的 `-N` 对 B 站单文件无效；aria2c 多连接打 Akamai 反而更糟（[02 §5](02-why-cdn.md#5-三个冷门视频的共同规律)） | 不推荐（针对这个问题） |
| 7 | BTR 桌面版、[Lanes][lanes] | — | — | 修改或注入官方客户端 | — | 桌面版见 [03 §8](03-btr-security-audit.md#8-桌面版和旧-chrome-插件请谨慎)；Lanes 会打开调试端口，本机任何进程都能操纵你的登录会话 | 不推荐 |
| 8 | DownKyi、downkyicore、BiliTools、BilibiliDown | — | 2026-07 停止维护 | — | — | 收到律师函后停止维护（仓库还在，但已标注弃用或归档）；网上转载的安装包不可信 | 不推荐 |

## C. 网络层

| # | 方案 | ⭐ / 最近活动 | 机制 | 是否对症 | 风险 | 结论 |
|---|---|---|---|---|---|---|
| 1 | **只让视频域名**走港 / 日中转（比如 mihomo 或 Clash Verge Rev 的规则组 `[DIRECT, HK, JP]`） | mihomo 34.8k★ · Clash Verge Rev 150.9k★ · Hysteria 22.7k★（都活跃） | www / api 保持直连（B 站看到的地区不变）；视频主机由中转节点在亚洲解析，长距离那一段交给节点 | ❓ **未经验证的假设**；前提是你本来就有可信的港 / 日直连节点；热门视频要切回 DIRECT | Clash Verge Rev ≤ 2.5.4 有本地提权漏洞（[公告][cvr]，请用 ≥ 2.5.8）；自建 Hysteria 服务端要用最新版；签名地址里带 `oi`（你的 IP），换出口可能返回 403（未测）；mihomo 实际是 GPL-3.0，默认分支是无关内容，请从 Releases 下载 | 进阶，最后再试 |
| 2 | 公共规则集（blackmatrix7、ACL4SSR、v2fly、elysias123） | blackmatrix7 28.2k★ · v2fly 9.7k★ · ACL4SSR 6.8k★ · elysias123 30★ | 只是“管道” | — | blackmatrix7 规则内容停在 2025-06；ACL4SSR 的港澳台规则停在 2023；elysias123 的示例会 REJECT Akamai；多数规则集把 www / api 和公共 DNS 的 IP 混在一起 | 只用 [v2fly][v2fly] 的 `geosite:bilibili-cdn` 加精确的 Akamai 主机，www / api 自己写 DIRECT；规则地址钉到具体提交 |
| 3 | 回国加速器（各类商业产品） | 商业闭源 | 让 B 站把你当成国内用户 | ❌ 换来的是长距离大陆线路加 PCDN，也没有任何独立测速 | 国内运营方能看到隧道里的全部流量；IP 属地和能看的内容会变；常见自动续费 | 不推荐（除非你要看大陆独占版权内容） |
| 4 | 游戏加速器、通用 VPN | 商业闭源 | 方向不对 | ❌ | 往往是内核驱动级软件 | 不推荐 |
| 5 | 自建大陆出口（亲戚家宽带、国内云） | — | 同 3 | ❌ | 法律灰区；家庭宽带上行异常可能被封 | 不推荐 |
| 6 | hosts 钉 IP（[akamTester][akt] 等）、DNS / ECS 技巧 | akamTester 376★（2025-03 停更） | 只是换一个边缘 IP | ❌ 海外 Akamai 通常已经解析到本地节点；时延低不等于吞吐高；跨 CDN 钉 IP 直接 TLS 失败 | 要改系统文件；akamTester 已停更，最新二进制是 2020 年的未签名 exe | 不推荐 |
| 7 | MITM 改写模块（[Biliverse/Redirect][bvr] 等） | 22★ | 由代理软件改写 CDN 地址 | 不适用于 Windows 上的 Chrome | 要信任根证书；某个 Shadowrocket 变体会把带 `mid` / `oi` 的签名地址发到第三方端点（泄露观看记录） | 不推荐 |
| 8 | 开着 Cloudflare WARP 看 B 站 | Cloudflare 官方 | 换成 Cloudflare 的出口 | ❌ 不会改变 B 站分配的节点，还多绕一段路（[WARP FAQ][warp]） | — | 测试和看 B 站时关掉 |
| 9 | Windows TCP“优化器”、BBR2、关闭 QUIC | — | 改本机传输参数 | ❌ 下载方向的拥塞控制由 CDN 服务器决定（[RFC 9438 §5.10][rfc]）；Win11 24H2 的 BBR2 会让本机代理卡死 | 改系统设置 | 不推荐（关 QUIC 最多做一次 A/B 测试） |

## D. 设置与诊断（零风险，先做）

| 方案 | 作用 | 说明 | 结论 |
|---|---|---|---|
| **打开浏览器硬件加速** | 硬件解码、硬件合成 | 荷兰案例的原因 A；见 [01 §2](01-diagnosis.md#2-第一步硬件加速开了吗) | **必做** |
| 播放策略选 HEVC 或 AV1 | 降低需要的码率 | Chrome 的 HEVC 只能硬解；AV1 只在 `chrome://gpu` 列出 `Decode av1 profile main` 时选；同画质下 AVC 码率是 HEVC 的 2.3–2.7 倍 | 必做 |
| 硬解自查：`chrome://gpu`、`chrome://media-internals`、[`decode-check.js`](../../tools/decode-check.js) | 排除解码卡顿 | 方法参考 [StaZhu 的指南][stazhu]（1.45k★） | 必做 |
| [`cdn-bench.js`](../../tools/cdn-bench.js)（本仓库） | 对比冷 / 热、单连接 / 并行、各个节点 | 思路参考 [chrisliu298 的 probe.js][cl] | 推荐 |
| B 站官方[测速页][diag]（加上 `?bvid=…&cid=…`） | 第一方测速 | 只测文件开头，而且是单连接，会低估冷门问题；不带参数时要登录，并会读你的观看历史 | 参考 |
| NVIDIA：VSR 设为自动或关闭；检查 G-SYNC 窗口模式；144 Hz 改成 120 / 60 Hz | 渲染和帧节奏 | 只在“掉帧或抖动，但不转圈”时有用 | 视情况 |
| [pakku.js][pakku] | 合并刷屏弹幕 | 只在“关掉弹幕就好”时有用 | 视情况 |
| Bilibili-Evolved、enhanced-h264ify、BewlyBewly | — | 都没有播放 CDN 或编码设置；h264ify 只管 YouTube 且已停更；BewlyBewly 已归档 | 不相关 |

**已停更超过 12 个月的项目**：Make BiliBili Great Again 原版（2024-12）、AkagiYui 的 PCDN 屏蔽（2024-10）、Bilibili-Old（2024-09）、akamTester（2025-03）。Greasy Fork #553929（2025-10）也接近停更。

## E. 法律与存续风险

B 站的律师事务所近一年陆续向一些第三方项目发函：PiliPala（2025-07）、bilibili-API-collect（2026-01，之后归档）、BiliRoaming（2026-07-06，函中把“改写 CDN 回源盗用平台分发资源”列为问题之一，[来源][roam]），以及 DownKyi、downkyicore、BiliTools（2026-07-06，之后停止维护）。

**BTR、realzza、CCB 和 MBGTEB 都属于改写 CDN 地址的这一类。** 这意味着：
- 它们可能随时失效或被下架。钉版本安装后，你的脚本管理器里会一直留着自己的那份副本。
- 使用它们**可能不符合 B 站用户协议**，请自行判断。

纯路由方案（§C-1）不改写地址，不在此列。

## F. 不推荐清单及原因

| 不推荐 | 原因 |
|---|---|
| BTR 桌面版 | `irm … \| iex` 安装、EXE 没有签名、需要 UAC 提权、开机自启、更新只靠同仓库里的哈希、维护者建议关闭智能应用控制；在浏览器里看 B 站用不到它（[03 §8](03-btr-security-audit.md#8-桌面版和旧-chrome-插件请谨慎)） |
| Releases 里的旧 BTR Chrome 插件 zip / .crx | 已停更，不会自动更新，没有逐字节核验；和脚本版同时开会重复接管 |
| CDNSpeedTest.exe（[Overseas Video Speedup][ovs] 配套） | 根据其仓库里 `tools/cdn-speedtest-app` 的 README 和代码：在开发者本机构建，没法从源码复现；必须用 B 站扫码登录；会上传出口 IP、城市、运营商、网络类型（含 Wi-Fi 信息）和使用记录；用明文 HTTP 查询 IP；会读取浏览器的配置文件；会自我更新；和抽奖活动绑定 |
| 商业回国加速器、游戏加速器、通用 VPN | 解决不了冷门回源；第三方能看到你的全部流量；会改变你的地区；PCDN 反而更慢 |
| hosts 钉 IP、akamTester、DNS / ECS 技巧 | 时延低不等于吞吐高；跨 CDN 直接失败；要改系统文件 |
| 开着 WARP 看 B 站 | 不改变分配的节点，只会更慢 |
| BBDown `serve`；登录状态下用默认的 `--force-http` | 无鉴权的 API 可以被网页利用来执行本地程序；SESSDATA 明文传输 |
| 同时开两个加速器（BTR + MBGTEB Thread Ripper / realzza / CDN 切换器） | 它们都在改同一批媒体请求，会互相打架，结果也没法解释 |
| Lanes | 会打开调试端口，本机任何进程都能操纵你的 B 站会话 |
| 自建大陆出口 | 法律和封号风险落在出口那一方 |
| BTR 改包和已停更的脚本（BiliThrottle、MBGA 原版、AkagiYui、Bilibili-Old、GF #553929） | 没有审计，或者已经停更 |
| Greasy Fork #588296 | 这是另一个同名为 “Bilibili Accelerator” 的独立脚本；要装 realzza，请认准 [#582026][rzgf] |
| Windows TCP“优化器”、BBR2 | 对下载无效，还可能关掉窗口自动调优，或让本机代理卡死 |

---

上一篇：[03 · BTR 安全审计](03-btr-security-audit.md) · 下一篇：[05 · 安全安装 BTR](05-safe-install.md)

<!-- 链接 -->
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
