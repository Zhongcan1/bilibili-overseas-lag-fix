# tools · 只读的诊断与校验工具

**中文** | [English](README.en.md)

三个浏览器控制台片段，加一个在本机运行的 Python 校验脚本，全部只读。

> ⚠️ **往开发者工具控制台里粘贴代码，等于把这个网页的全部权限交给这段代码。** 下面三个控制台片段都很短、没有压缩或混淆，你可以（也应该）先从头读一遍再用。**陌生人发来的控制台代码一律不要粘贴。**
> 第一次粘贴时，Chrome 会拦下并提示你先手动输入 `allow pasting`（中文界面可能是"允许粘贴"，以提示为准）。

| 文件 | 干什么 | 网络 | 对页面的改动 |
|---|---|---|---|
| [`decode-check.js`](decode-check.js)（约 120 行） | 查**硬件加速与解码**：WebGL 渲染器（标出 SwiftShader 等软件渲染）、AVC / HEVC / AV1 在 1080p60 和 4K60 下的解码能力、B 站播放策略，最后给出结论 | **不发任何请求** | 创建一个不插入页面的 canvas 读 WebGL 信息，读完即释放；结果放在 `window.__decodeCheck` |
| [`cdn-bench.js`](cdn-bench.js)（约 270 行，其中约 75 行是中英注释） | 测各个 B 站视频节点对**当前视频**的吞吐与首字节时间：冷数据、单连接 vs 并行，最后给出"结论提示" | 只连 B 站视频 CDN，不带 Cookie，默认约 40 MB（按节点数自动计算） | 临时插入一个隐藏的空白 iframe（借原生 fetch），结束即删；结果放在 `window.__cdnBench` |
| [`play-monitor.js`](play-monitor.js)（约 100 行） | 记录首帧时间、卡顿次数和时长、拖动后的等待、前方缓冲、丢帧，用于 A/B 对比 | **不发任何请求** | 只给 `<video>` 加事件监听；结果放在 `window.__pm` |

| 本机脚本 | 干什么 | 网络 | 对浏览器的改动 |
|---|---|---|---|
| [`verify-tm-install.py`](verify-tm-install.py)（Python 3.8+，只用标准库） | 核对 Tampermonkey **实际存下来**的 BTR：正文是否与审计提交 `0302b34` 逐字节一致、文件头是否按 [05](../docs/zh-CN/05-safe-install.md) 改好、「检查更新」是否已关闭，最后给出 PASS / FAIL | **不联网、不下载** | **无**：只读打开 Tampermonkey 的存储文件，读进内存，不写任何文件 |

**建议顺序**：先 `decode-check.js`（30 秒，排除本机播放问题）→ 还卡、而且只有冷门视频卡，再 `cdn-bench.js`（排查网络 / CDN）→ 按 05 装好 BTR 后用 `verify-tm-install.py` 确认装对了 → 用 `play-monitor.js` 做 A/B 对比。整体流程见 [01 诊断](../docs/zh-CN/01-diagnosis.md)。

三个控制台片段都按 Chromium 内核浏览器（Chrome / Edge）写的；其他浏览器没有测过。所有提示都是"中文 / English"双语。代码以 MIT 许可发布，见 [`LICENSE`](../LICENSE)。

---

## decode-check.js：先排除"本机放不动"

很多"卡顿"其实和网络无关：浏览器的**"使用图形加速功能（如果可用）"被关掉**（或 GPU 被禁用）时，1080P60 视频要靠 CPU 软解、画面和弹幕也要靠 CPU 软件合成，网速再快也会掉帧。这个片段几秒钟就能看出来。

**用法**
1. 打开任意 `www.bilibili.com` 页面（在别的网站也能跑，只是读不到 B 站的播放策略）。
2. F12 → Console → 粘贴整个文件 → 回车。

**它报告什么**

| 项目 | 怎么得到的 | 怎么看 |
|---|---|---|
| 浏览器版本 | `navigator.userAgentData`（没有则用 UA 字符串） | 去 `chrome://settings/help`（Edge：`edge://settings/help`）确认是最新版；那里报错或一直卡住，说明自动更新可能已经静默失效，从官网（google.com/chrome）重新安装即可，个人资料会保留 |
| WebGL 渲染器 | WebGL 的 `UNMASKED_RENDERER_WEBGL`（读不到时用 `RENDERER`） | 含 `SwiftShader`、`llvmpipe`、`Basic Render` 等，或者根本没有 WebGL → 在用软件渲染 |
| 解码能力表 | `navigator.mediaCapabilities.decodingInfo`，类型 `media-source`（B 站播放器用的就是 MSE） | 见下表 |
| B 站播放策略 | `localStorage['bilibili_player_codec_prefer_type']`：`0` 或未设置 = 默认，`1` HEVC，`2` AVC，`3` AV1 | 和建议的编码对照 |

解码能力表每行一种"编码 × 规格"：

| 列 | 含义 |
|---|---|
| 能解码 supported | 浏览器能不能播这种格式。Chrome 的 HEVC 播放依赖硬件解码，所以 HEVC 为 `false` 往往说明没有 HEVC 硬解 |
| 流畅 smooth | 浏览器认为能否流畅播放；Chrome 可能参考本机过去的播放统计 |
| 省电≈硬解 powerEfficient | 在 Chrome 里为 `true` 通常表示有硬件解码。**1080p60 三种编码都是 `false` 是最值得警惕的信号** |

查询用的参数：1080p60 = 1920×1080、60 fps、6 Mbps，编码字符串 `avc1.640032` / `hev1.1.6.L123.90` / `av01.0.09M.08`；4K60 = 3840×2160、60 fps、20 Mbps，`avc1.640034` / `hev1.1.6.L153.90` / `av01.0.13M.08`。B 站实际视频流的编码字符串可能略有不同，结果是方向参考。

**结论的几种情况**

| 控制台里出现 | 意思 | 怎么办 |
|---|---|---|
| ⚠ 浏览器在用软件渲染 / 没有 WebGL | "使用图形加速功能"多半被关了，或 GPU 被禁用 | `chrome://settings/system`（Edge：`edge://settings/system`）打开它 → 点"重新启动" → 再跑一次 |
| ⚠ 1080p60 下都没有报告硬件解码 | CPU 软解 | 先修上一条；修好后到 `chrome://gpu` 确认 *Video Decode: Hardware accelerated*。修好之前播放策略用 AVC、清晰度用 1080P（不要 60 帧）或更低 |
| 建议播放策略：HEVC 或 AV1 | 有硬解，而且同画质下码率通常比 AVC 低 | 播放器 ⚙ →「更多播放设置」→「播放策略」，选好后刷新页面（界面可能随 B 站版本变化） |
| 当前是 默认（默认档……可能选 AV1……） | 默认档在浏览器报告能播 AV1 时可能选 AV1，而你的 AV1 是软解 | 手动选建议的编码 |
| ✓ 硬件加速看起来正常 | 本机播放链路没发现问题 | 还卡的话，下一步用 `cdn-bench.js` 查网络 |

**局限**：这些都是浏览器的"能力声明"，不是实测；最终以 `chrome://gpu` 和 `play-monitor.js` 记录的丢帧为准。**输出里有你的显卡型号**，公开分享截图前可以删掉。

---

## cdn-bench.js：冷门视频为什么卡

**用法**
1. 测"基线"前：在脚本管理器里**停用所有 B 站加速脚本**（BTR、MBGTEB、realzza…，它们会改写页面的 fetch），VPN / WARP / 代理保持关闭，笔记本插电。
2. **最好先登录**。打开 `https://www.bilibili.com/video/BV…`，清晰度切到你平时看的那一档，按 **F5 刷新**（站内跳转后 `__playinfo__` 不会更新），画面出来后立刻**暂停**。
3. F12 → Console → 粘贴整个文件 → 回车。等 1–6 分钟。
4. 看表格和最后的"结论提示"；`copy(JSON.stringify(__cdnBench))` 可以把结果复制出来保存。

**它做什么**：读 `window.__playinfo__`，找到正在播放的那条视频轨（优先用页面已经请求过的 `.m4s` 路径匹配）；对"B 站分配的主/备节点 + 3 个海外 + 6 个大陆 upos 节点"，各做 1 次单连接（2 MB）和 1 次 8 路并行（共 2 MB）的 Range 下载。每个节点、每次测试用文件 25%–90% 之间**不同的、随机错开的**区间，尽量读"没人读过的冷数据"。非 Akamai 节点通过"换主机名"复用 B 站签发的地址；Akamai 只测它自己的地址（Akamai 地址换主机后能不能用，各项目说法相互矛盾，为免误判不拿它换）。

**它不做什么**：不带 Cookie（`credentials:'omit'`）；每个请求发出前检查主机，只允许 `*.bilivideo.com` / `*.bilivideo.cn` 和 B 站分配的 `upos-*.akamaized.net`；不调用 B 站 API；不改设置或存储；不上传；控制台里只打印主机名，**不打印签名地址**（签名地址里含账号 ID 和 IP）。

**可调参数**（文件开头的 `CFG`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `OVERSEAS` / `MAINLAND` | 3 个 / 6 个 | 要测的节点（只接受 `*.bilivideo.com`） |
| `EXTRA` | 空 | 额外节点，例如 `upos-sz-mirrorhwo1.bilivideo.com`、`upos-sz-mirror08h.bilivideo.com`。每多一个节点约多 4 MB 流量（`BUDGET_MB` 为 0 时预算自动跟着加） |
| `SINGLE_MB` | 2 | 单连接样本。改成 8 可减少 TCP 慢启动造成的低估（从欧洲到大陆节点往返常在 200–330 ms）。`BUDGET_MB` 保持 0 会自动放大到约 100 MB；若你手动设了 `BUDGET_MB`，要同时改到 ≥ 110 |
| `PAR` / `PAR_MB` | 8 / 2 | 并行路数 / 并行样本合计大小 |
| `BUDGET_MB` | 0 | 样本总流量上限（MB）。0 = 自动：节点数 ×（单连 + 并行样本）+ 4 MB 余量，默认 10 个节点约 40 MB，保证每个节点都测到。填数字 = 手动上限：不够时控制台先提示，排在后面的节点会被跳过 |
| `TIMEOUT_S` | 15 | 单个请求最多等多久；超时也会按已收到的字节算速度 |
| `QN` | 0 | 指定清晰度 id：16=360P、32=480P、64=720P、80=1080P、112=1080P+、116=1080P60、120=4K；0 = 自动 |
| `TARGET_MBPS` | 0 | "结论提示"按多少 Mbps 码率判断；0 = 用当前视频轨的码率。**未登录时播放器常常只给 360P/480P（0.3–0.6 Mbps）**，这时结论会偏乐观（几乎总是判成"热"）——请登录后用常看的清晰度测，或填 6（≈1080P+） |

**结果怎么看**（表格列名是"中文 英文"双语）

| 列 | 含义 |
|---|---|
| 节点 node / 类型 role | 主机名；类型为 分配-主 / 分配-备（B 站分配给你的）、海外、大陆、额外 |
| 单连 single Mbps / TTFB ms | 一条连接的速度 / 首字节时间（含建连）。B 站原生播放器就是这种方式 |
| 并行 parallel×N Mbps | 同样字节数拆成 N 段同时下载的总速度（多连接加速脚本的上限参考） |
| ÷码率 ÷bitrate | 速度除以这条视频轨的码率（设了 `TARGET_MBPS` 时除以该值，控制台会提示）。**≥ 1.5 才算"有余量"** |
| 备注 note | `超时`（速度按超时前已收到的字节计算，所以标了"超时"的行也可能有非零 Mbps，这不矛盾）、`HTTP 403`（拒绝）、`HTTP 200`（节点不支持 Range，已立即中止）、`HTTP 416 超出文件末尾`、`Range不符`（Content-Range 对不上）、`多余数据`（收到的字节比请求的多）、`网络错误`、`中止`、`超出流量预算，跳过`（只在手动设了 `BUDGET_MB` 时出现）。前缀 `单连:` / `并行:` 分别表示单连接 / 并行。`__cdnBench.rows[*].s.note` 是单连接的备注，`pNote` 是并行的 |

**"结论提示"与下一步**

| 结论提示（开头） | 意思 | 下一步 |
|---|---|---|
| B 站分配的主节点单连接已 ≥1.5× 码率 | 这个视频对你是"热"的，CDN 不是瓶颈 | 回到 [01 诊断](../docs/zh-CN/01-diagnosis.md)：硬件加速、解码、扩展冲突 |
| 换个节点、单连接就 ≥1.5× 码率 | 换个节点就够，不一定需要多连接 | 轻量的单连接换源脚本（如 [realzza/bilibili-accelerator](https://github.com/realzza/bilibili-accelerator)）可能就够，见 [04 替代方案](../docs/zh-CN/04-alternatives.md) |
| "大陆 + 并行"能到 1.5× 码率 | 需要"大陆节点 + 多连接" | [BTR](https://github.com/MrTangLuyao/Bilibili-thread-ripper)（钉版本安装，见 [05](../docs/zh-CN/05-safe-install.md)）或 [MBGTEB](https://github.com/SukkaW/Make-Bilibili-Great-Than-Ever-Before) 的 Thread Ripper 这类方案，值得做 A/B 测试 |
| 只有"海外 + 并行"能到 1.5× 码率 | 多连接有用，大陆节点帮不上 | 同上（BTR 的海外模式） |
| 大陆、海外节点加上并行都不到 1.5× 码率 | 整条网络都不够 | 降清晰度、用 HEVC/AV1（需硬件解码），或用官方客户端离线缓存 |
| 分配节点不够快，但只拿到 Akamai 地址 | 没法测别的节点 | F5 刷新换一批地址，或换个视频再测 |

为什么冷门视频特别慢、各次实测的数据，见 [02 为什么是 CDN](../docs/zh-CN/02-why-cdn.md)。

**常见问题**
- *提示没找到 `__playinfo__`*：按 F5 刷新视频页再试；番剧、付费、地区受限页面可能没有这项数据。
- *提示签名地址已过期*：页面开太久了，F5 后重跑。
- *一些节点显示"超出流量预算，跳过"*：你手动设了 `BUDGET_MB` 而且太小（控制台开头会有 ⚠ 提示）；改回 0（自动）再跑。
- *所有节点都是 0 / 网络错误*：确认没开代理 / WARP、没有广告拦截类扩展拦截 `bilivideo.com`；换个视频再试。
- *同一个冷门视频测第二次明显变快*：正常，数据被测"热"了，换一个没看过的冷门视频。
- *数字和加速脚本面板里的不一样*：`cdn-bench` 测的是"节点能给多快"，脚本面板显示的是它实际调度的结果，两者不等价。

**局限**：每个节点只测一次，结果只作方向参考；同 IP 的节点（hw/08c/08h…）不是独立线路，多个节点的并行速度不能相加；HTTP/2 下同一主机的并行请求共用一条连接；单连接测试在前（含建连）、并行在后（复用连接），并行数字略偏乐观；不同时段差异大（大陆晚高峰约为北京时间 19–23 点）。

---

## play-monitor.js：A/B 对比时客观记数

1. 播放器设置里关掉「自动开播」，按 F5 刷新视频页，**先不要点播放**。
2. F12 → Console → 粘贴 → 回车；然后点播放，正常看 3 分钟（按计划拖动进度）。
3. 每 10 秒打印一行；结束时输入 `__pm.stop()`，打印汇总表（也存在 `__pm.summary`）。

汇总表的列：观察秒数、首帧 ms（从按下播放到开始播放）、卡顿次数（不含拖动）、卡顿总秒、拖动后等待次数、拖动等待总秒、当前前方缓冲 s、最小前方缓冲 s、丢帧/总帧、丢帧率 %。

只读 `<video>` 的状态与事件，不改页面、不发请求。按审计时的 BTR 代码（提交 `0302b34`），BTR 接管播放后仍使用页面原有的 `<video>`，所以理论上同样适用（未实测）。站内跳转到别的视频后请重新粘贴；B 站的 WASM 播放器 `<bwp-video>` 不支持。A/B 测试的完整步骤和通过标准见 [05 安全安装](../docs/zh-CN/05-safe-install.md)。

---

## verify-tm-install.py：确认装的就是审计过的那份

装好 BTR 以后，[05 §2 ⑤](../docs/zh-CN/05-safe-install.md) 要你在编辑器里逐行核对。这个脚本把这些核对自动做一遍，而且看的是 Tampermonkey **实际存下来、实际会运行**的那份代码，不是界面上显示的版本号。几十万字节的代码，人眼比不出"改了一个字符"，SHA-256 可以。

**它检查什么**（每项 PASS / FAIL；FAIL 附修复提示，指向 05 的具体步骤）

| 检查 | 通过条件 |
|---|---|
| 版本 | 文件头 `@version` 和 Tampermonkey 记录里的版本都是 `2026.10.8.1` |
| 正文 | `// ==/UserScript==` 之后的全部代码与审计提交 `0302b34` 逐字节一致（SHA-256 `793c4bc8…`，404,509 字节，写在脚本里，运行时不联网）。只差 CRLF 换行也算通过，会注明 |
| 文件头外无代码 | 文件头里只有 `//` 注释行，文件头前面没有任何内容（这两处的代码同样会被执行） |
| `@updateURL` / `@downloadURL` | 各有且只有一行，值为 `none`（§2 ③A） |
| 检查更新 | Tampermonkey 记录里的 `options.check_for_updates` 为 `false`（§2 ③B） |
| 4 条排除规则 | passport / pay / account / member 四个子域都被排除；写在文件头或「用户排除」里都算，但「原始排除规则」被关掉时不算（§2 ④） |
| `@run-at` | 只有一行 `@run-at document-start`，而且没有任何一行里出现两个 `// @`（§2 ④ 说的粘行问题） |
| `@grant` | 正好是那 6 项 |
| 范围 | 没有 `@require`、`@resource`、`@connect`、`@include`；`@match` 仍只有 `https://*.bilibili.com/*`；Tampermonkey 设置里也没有另加匹配规则 |
| 其余文件头 | 除了上面允许的改动，与审计版本逐行一致（`@sandbox`、`@inject-into`、`@namespace` 等） |

另外列出、但不影响结论的：脚本是否启用；Tampermonkey 内部记录的更新地址；安装来源是不是钉提交地址；最后修改时间；有没有装了多份；是不是 BETA 版。

**用法**（Python 3.8 或更新版本；Windows 可从 python.org 安装，下面的 `python3` 在 Windows 上换成 `py` 或 `python`）

```
python3 verify-tm-install.py                 # 自动查找 Chrome / Edge / Brave / Chromium / Opera 的所有个人资料
python3 verify-tm-install.py --browser chrome --profile "Default"
python3 verify-tm-install.py --profile-dir "<个人资料路径>"
python3 verify-tm-install.py --audited-file bilibili-thread-ripper.user.js   # 可选，见下
python3 verify-tm-install.py --lang zh        # 只显示中文（en = 只显示英文；默认双语）
python3 verify-tm-install.py --self-test      # 自检内置的 LevelDB / Snappy 读取器
```

- 个人资料路径在 `chrome://version`（Edge：`edge://version`）的「个人资料路径」一行。
- `--audited-file`：按 [05 §2 ①](../docs/zh-CN/05-safe-install.md) 的提示另存下来的钉版本文件。脚本先核对它的 SHA-256，正文不一致时再用它指出第一处差异在第几行。
- 默认找 Tampermonkey 官方的 6 个扩展 ID（[FAQ Q406](https://www.tampermonkey.net/faq.php?locale=en&q=Q406#Q406)：正式版、BETA、Legacy，Chrome / Edge / Opera 商店）；其他 ID 用 `--ext-id` 补充。脚本名称改过的话，也会按 `@namespace` 找到；`--name` 可以指定别的名称。
- 浏览器开着也能跑。退出码：0 = PASS，1 = FAIL，2 = 没找到或出错，方便写进自己的定期检查。

输出示例（节选；这正是「只做了 ③A、没做 ③B」时的样子）：

```
== Chrome · Default · Tampermonkey (Chrome Web Store) ==
  [PASS] 正文（实际运行的代码）与审计提交 0302b34 逐字节一致
  [PASS] @updateURL none
  [PASS] @downloadURL none
  [FAIL] 「检查更新」仍是勾选状态（options.check_for_updates = true）
         → 修复：脚本的「设置」标签页 → 取消勾选「检查更新」→ 保存（05 §2 ③B）
  [PASS] 4 条敏感子域排除规则都在
  [PASS] @run-at document-start 独占一行，没有粘连的行
  ...
  结论：FAIL，1 项未通过（见上方 → 修复）。
```

**它读什么、怎么读**

Tampermonkey 把脚本存在 `chrome.storage.local` 里，也就是个人资料下的 `Local Extension Settings/<扩展 ID>` 文件夹，底层是 LevelDB。脚本**只读这一个文件夹**，并且按 LevelDB 的格式逐层解析，而不是在文件里搜文本：

- **`.log`（预写日志）**：按 32 KiB 一块、每条记录 7 字节头（CRC32C、长度、类型），把 FULL / FIRST / MIDDLE / LAST 分片拼回完整记录，校验 CRC，再解析里面的 WriteBatch（序列号、条数、逐条的键和值）。一个 40 万字节的脚本会跨十几个块，直接搜字符串会被块头切断、拼出错误的内容；
- **`.ldb`（表文件）**：解析 footer、索引块和数据块，内置纯 Python 的 Snappy 解压，逐块校验 CRC32C；
- **`MANIFEST`**：确定哪些 `.log` / `.ldb` 仍然有效，忽略已经过时的文件；
- 同一个键以序列号最大的记录为准（删除也算），所以看到的是 Tampermonkey 此刻的状态，而不是某个历史版本。

用到的键：`@source#…`（脚本全文）和 `@meta#…`（Tampermonkey 解析出的元数据和这个脚本的设置）。

**隐私与安全**

- **只读**：每个文件用只读方式打开（Windows 上允许其他程序同时读、写、删除，不会挡住浏览器），读进内存后立即关闭。**不写任何文件**（包括临时文件），不联网，不下载，不调用浏览器。
- **只打印匹配到的那个脚本**。其他脚本的名称、代码、设置和存储的数据都不打印，只报一个"共 N 个已安装脚本"的数字。
- 不打印脚本 ID 和本机路径。更新地址只显示 `none`、钉提交地址或 main 地址，其他 https 地址只显示域名，本地文件地址不显示。所以输出可以直接贴进 issue。
- Cookie 不在这个文件夹里，脚本也不会去读。
- 代码约 1,100 行，没有压缩或混淆，只依赖 Python 标准库；其中约一半是 LevelDB / Snappy 读取器和自检。

**局限**

- 只支持 Chromium 内核浏览器里的 Tampermonkey。Violentmonkey、Firefox、Safari 不支持；Violentmonkey 请按 [05 §3](../docs/zh-CN/05-safe-install.md) 第 4 步手动核对。
- 只核对存储里的记录。BTR 在页面上是否真的生效、passport 页面是否真的被排除，仍要按 05 §2 ⑤ 在浏览器里看一眼。
- 不读 Tampermonkey 的全局设置，所以不检查可选的 §2 ③C（全局更新间隔）。
- 表文件只支持无压缩和 Snappy 两种块格式。遇到别的格式时会提示并跳过那些块；这时在 Tampermonkey 里对 BTR 做一次改动（比如停用再启用），最新记录就会写进 `.log`，重跑即可。
- 依赖 Tampermonkey 现在的存储格式（键名 `@source#` / `@meta#`、设置项 `options.check_for_updates`），2026-10-13 在 Tampermonkey 5.5.1 上确认过；以后的版本如果改了格式，可能会读不到或报"读不到设置"。
- 只认审计过的提交 `0302b34`（v2026.10.8.1）。按 [05 §4](../docs/zh-CN/05-safe-install.md) 升级到新提交后，正文和版本两项会报 FAIL，这是预期的：新版本要先经过复审。
- 正文一致只说明代码与审计时相同。审计本身查了什么、没查什么，见 [03](../docs/zh-CN/03-btr-security-audit.md)。

---

## 测试情况（如实说明）

**cdn-bench.js**
- **模拟环境**：用假的 `__playinfo__` 和假的 CDN 响应（没有任何真实网络请求）覆盖了：混合故障（超时 / 403 / 200 / Range 不符 / 多余数据 / 网络错误）、冷门慢节点、只有 Akamai 地址、没有 `__playinfo__`、过期的 `__playinfo__` + 读不到文件大小、非法主机（被忽略）、自动与手动流量预算、"结论提示"除"拿不到码率"以外的每个分支。（"指定清晰度 `QN`"和"拿不到码率"两种情况没有被模拟测试覆盖。）检查项：所有请求都是 `credentials:'omit'`、只连允许的主机、字节区间互不重叠且落在文件中段、总量与开头打印的计划一致、iframe 用完即删、结果里没有签名地址。
- **真实 B 站页面，未登录**（2026-10-13，v1.1 之前的版本，Chromium 内核浏览器）：冷门视频 BV1EqYE6iEu5（64 次播放、约 3 小时）完整跑通，10 个节点全部测完、约 40 MB、表格与"结论提示"正常、iframe 已移除、结果里没有签名地址。这次实跑暴露了一个问题：未登录只拿到 360P（0.40 Mbps），按这个码率会误判成"热"——v1.1 因此加了 `TARGET_MBPS` 和低码率警告。
- **真实 B 站页面，已登录**（2026-10-13，Chrome，同一套测速逻辑）：冷门视频 BV1wqbT6AEbe（65 次播放、约 4 小时、1080P60 AVC、声明码率 3.48 Mbps）测完 10 个节点。数据和解读见 [02](../docs/zh-CN/02-why-cdn.md)。
- **本双语版**：只改了注释、控制台提示文字和表格列名，**测速逻辑与 v1.1 相同**。两项核对：① 用一个小型分词脚本对比新旧两版：去掉注释后词法单元数量相同，除字符串文字外唯一的差别是表格的 3 个列名（`节点`、`类型`、`备注` 从标识符写法改成带引号的双语字符串，只影响显示）；② 在同一个模拟环境里把上面 13 个场景对新旧两版各跑一遍：请求次数、连接的主机、字节区间、总流量、iframe 删除、结果对象、表格各行和"结论提示"分支全部一致。双语版本身没有在真实 B 站页面上重新跑过。

**play-monitor.js**
- **模拟环境**（较早）。
- **本地测试页**（2026-10-13，Chromium 内核浏览器）：用浏览器现场生成的 WebM 视频，加上人工触发的 `waiting` / `playing` 事件：卡顿次数与时长、拖动后等待次数、每 10 秒一行的日志、`__pm.stop()` 汇总表、"没找到 `<video>`"的提示都正常。
- **真实 B 站页面**（2026-10-13，未登录，Chromium 内核浏览器，硬件加速开启，粘贴的代码与本文件一致）：热门视频 BV15KpR6TENe 播放约 30 秒、拖动 1 次：首帧时间、每 10 秒的日志、拖动后等待次数、前方缓冲、丢帧和汇总表都正常输出。
- **还没测过**：冷门视频上真实发生的卡顿；BTR 接管播放时。

**decode-check.js**（本次新写）
- **模拟环境**：伪造 WebGL 和 `mediaCapabilities` 的回答，覆盖 10 种情况：SwiftShader + 三种编码都没有硬解（即案例中的情况）、全部硬解、只有 HEVC 硬解且播放策略为默认、选了 AVC 但 HEVC 有硬解、没有 WebGL、没有 `mediaCapabilities`、不在 bilibili.com、查询被拒绝 + 没有 `userAgentData`、只有 AVC 硬解、未知的播放策略值。每种情况的结论都符合预期，没有报错，canvas 用完即释放。
- **真实 B 站页面**（2026-10-13，未登录，同上的浏览器，粘贴的代码与本文件一致）：立即出结果；六项查询都报告 supported / smooth / powerEfficient = true，结论为"✓ 硬件加速看起来正常"并建议 HEVC 或 AV1；页面上没有留下 canvas。
- **还没测过**：在真正关掉硬件加速的浏览器里运行。"软件渲染 / 没有硬解"这条结论目前只在模拟环境里验证过。

**verify-tm-install.py**（本次新写）
- **自检**（`--self-test`）：CRC32C 标准测试值、Snappy 解压（含重叠复制和两种损坏输入）、跨块的 FIRST / MIDDLE / LAST 分片、WriteBatch 解析、损坏的分片被丢弃。
- **模拟场景**：16 种文件头 / 设置组合，结论都符合预期。通过的：按指南改好、CRLF 换行、排除规则写在「用户排除」里、文件开头有 BOM；不通过的：「检查更新」仍勾选、读不到设置、「原始排除规则」被关掉、多了 `@require`、文件头前有代码、文件头里有非注释行、正文改了一个字符、多了 `@grant GM_cookie`、设置里另加了匹配规则、未修改的发布文件、改了 `@name`；只警告的：脚本停用 + 运行时机被覆盖。另用一份合成的 LevelDB 日志端到端跑过一次：改名后的脚本按 `@namespace` 找到，`--audited-file` 正确指出第一处差异的行号，同一存储里的另一个脚本没有出现在输出里。
- **损坏输入**：对真实存储的副本（`.log`、`.ldb`、`MANIFEST`）随机改写字节、随机截断，各 60 轮，外加 300 段随机 Snappy 数据：没有崩溃，损坏的部分被跳过并计数。
- **真实存储**（2026-10-13，Windows，Chrome，Tampermonkey 5.5.1，浏览器开着）：
  - 当前存储：不到 1 秒读完 1 个 `.log` 和 1 个 `.ldb`。正文逐字节一致；`@updateURL` / `@downloadURL` 为 `none`；4 条排除规则、`@run-at`、6 项 `@grant`、范围、其余文件头都通过；唯一的 FAIL 是「检查更新」仍勾选。这和 [05 §2 ③B](../docs/zh-CN/05-safe-install.md) 记下的现象一致：只改文件头，这个开关不会跟着关掉。
  - 同一天早些时候的一份存储副本（刚改完文件头时）：工具指出了 §2 ④ 说的粘行，`// @exclude      https://member.bilibili.com/*// @run-at       document-start`，并据此报告 member 排除规则缺失、`@run-at` 丢失。
  - 表文件：313 个数据块全部通过 CRC 校验并成功解压，键的顺序符合 LevelDB 的排序规则。
  - 一个装了 Tampermonkey 但没有任何脚本的个人资料：报告"没有找到 BTR"，退出码 2。
  - 在 Python 3.11、3.12、3.13 上跑过；语法按 3.8 检查过。
- **还没测过**：macOS 和 Linux；Edge、Brave、Opera、Chromium 里真的装了 BTR 的情况；Tampermonkey BETA；Python 3.8–3.10 实机运行。

如果你在自己的浏览器里运行时报错，欢迎提 issue，附上控制台截图（先删掉显卡型号等你不想公开的信息）。
