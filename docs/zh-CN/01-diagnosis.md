# 01 · 诊断：是“缓冲”还是“解码”？

**简体中文** · [English](../en/01-diagnosis.md) · [← 返回首页](../../README.md)

> **一句话**：先排除本地播放链路，尤其是硬件加速，再去怀疑网络。查本地免费、零风险，而在我们的荷兰案例里，这恰好就是被忽略的那一半原因。

## 1. 两类卡顿，表现不一样

| 你看到的现象 | 更可能是 | 去哪里 |
|---|---|---|
| 转圈；声音和画面一起停；灰色缓冲条追上播放点；**只有冷门视频**这样 | **缓冲**（网络 / CDN） | [02 · 原因与实测](02-why-cdn.md) |
| 不转圈；声音继续、画面一顿一顿；缓冲条远远领先；丢帧数一直在涨；**热门视频也这样** | **解码 / 渲染**（本地） | 本文 §2–§5 |
| 不丢帧、缓冲也充足，但画面节奏不匀 | 刷新率节奏不匹配（比如 144 Hz 屏幕放 60 帧），或 G-SYNC 窗口模式 | §5 |
| 关掉弹幕就好了 | 弹幕渲染负担太重 | §5 |
| 在访客窗口（没有扩展）里就好了 | 某个扩展或脚本 | §5 |

两类原因**可以同时存在**。荷兰案例就是这样：硬件加速是关的，冷门视频的 CDN 又慢。

## 2. 第一步：硬件加速开了吗？

### 为什么它这么重要

浏览器的「使用图形加速功能」一旦关掉，会发生这些事：

- **视频解码**全部交给 CPU；
- **页面合成和 WebGL** 改由 [SwiftShader](https://github.com/google/swiftshader) 处理，也就是 Chrome 内置的 CPU 软件渲染器；
- Chrome 的 **HEVC 只能靠硬件解码**（Chromium 源码 [`media/media_options.gni`](https://github.com/chromium/chromium/blob/main/media/media_options.gni) 注明 HEVC 解码必须由平台提供），所以关掉硬件加速后 HEVC 直接不可用；**AV1** 会退回 CPU 软解（dav1d）。

最后往往只剩 **AVC**。可同画质下，AVC 恰恰是码率最高的编码（见 §4），于是压力又转回到网络上。

### 荷兰案例里看到的情况

案例中的电脑，显卡本身能硬解这三种编码，问题只出在浏览器里的一个开关上：

| 检查项 | 观察到的值 | 含义 |
|---|---|---|
| 设置 | 「使用图形加速功能（如果可用）」**关闭**（配置文件 `Local State` 里 `hardware_acceleration_mode.enabled = false`） | 硬件加速被禁用 |
| GPU 进程启动参数 | `--use-angle=swiftshader-webgl` | WebGL 走 CPU |
| WebGL 渲染器 | `SwiftShader` | 软件渲染 |
| `navigator.mediaCapabilities`（1080p60） | HEVC `supported=false`；AVC `smooth=false`；AVC / HEVC / AV1 的 `powerEfficient` 都是 `false` | 浏览器自己报告：没有硬件解码，AVC 也放不流畅 |
| B 站下发的视频轨 | 只有 AVC（`codecid 7`） | 用不了 HEVC 和 AV1 |

所以，**1080P60 AVC 的 CPU 软解，加上软件合成，再加上弹幕，网速再快也会卡**。修好它不用花一分钱，也不用装任何东西。

### 怎么检查（约 2 分钟）

| 在哪里 | 看什么 | 正常（硬件加速） | 有问题（软件） |
|---|---|---|---|
| `chrome://settings/system`（Edge：`edge://settings/system`） | 「使用图形加速功能（如果可用）」（Edge 上叫「在可用时使用图形加速」，各版本文字可能略有不同） | 打开 | 关闭 |
| `chrome://gpu` →「Graphics Feature Status」 | *Video Decode*、*WebGL* | *Hardware accelerated* | *Software only* / *Disabled* |
| `chrome://gpu` → 驱动信息里的 GL / ANGLE 渲染器 | 渲染器名称 | 你的显卡型号 | 含 *SwiftShader* |
| `chrome://gpu` →「Video Acceleration Information」 | 解码条目 | 有 `Decode h264 high`、`Decode hevc main`，较新的显卡还有 `Decode av1 profile main` | 空 |
| `chrome://media-internals` → Players → bilibili 那一项（要先播放视频） | `kVideoDecoderName`、`kIsPlatformVideoDecoder` | 例如 `D3D11VideoDecoder` + `true` | `Dav1dVideoDecoder` / `FFmpegVideoDecoder` + `false` |
| Windows 任务管理器 → 性能 → GPU →（把一个小图切到「Video Decode」） | 播放时的 Video Decode 占用 | 大于 0 | 一直是 0，而浏览器 CPU 占用很高 |

**最省事的办法**：在 B 站视频页按 F12 打开控制台，粘贴只读的 [`tools/decode-check.js`](../../tools/decode-check.js)。它会报告：

- WebGL 渲染器，是 SwiftShader 时会标出来；
- AVC / HEVC / AV1 在 1080p60 和 4K 下的 `supported` / `smooth` / `powerEfficient`；
- 你在 B 站播放器里选的播放策略。

最后它会用中英文给出一句结论。这个脚本不发任何网络请求。

### 怎么修

1. 打开「使用图形加速功能（如果可用）」，**一定要点「重新启动」**。只改开关不重启，不会生效。
2. 重启后再看一次 `chrome://gpu`。如果开关已经打开，却仍然显示 SwiftShader 或 *Software only*，常见原因有这几种：
   - **显卡驱动太旧或有已知问题**：看 `chrome://gpu` 里的「Problems Detected」，到显卡厂商官网更新驱动。
   - **策略锁定**：`chrome://policy` 里如果有 `HardwareAccelerationModeEnabled = false`，说明是单位或其它软件设置的，需要找管理员。
   - **远程桌面或虚拟机**：这类环境往往只有软件渲染。
3. 笔记本：插上电源；`chrome://settings/performance` 里关掉「节能模式」。节能模式会降低视频帧率（[9to5Google](https://9to5google.com/2022/12/08/google-chrome-memory-energy-saver/)），用电池或电量低时可能自动打开。

**Firefox 用户**：`about:support` →「图形」里，如果「合成」显示 *WebRender (Software)*，说明是软件渲染；「媒体」部分可以看到各编码是否支持硬件解码。名称会随版本略有不同。

## 3. 浏览器版本：自动更新可能静默失效

- 打开 `chrome://settings/help`（Edge 为 `edge://settings/help`），它会检查并下载更新，完成后点「重新启动」。
- **自动更新可能悄悄坏掉，你却完全察觉不到。** 比如在 Windows 上，Chrome 更新程序依赖的系统服务如果丢失了，更新日志里会出现 `0x80070424`（`ERROR_SERVICE_DOES_NOT_EXIST`），浏览器可能一年多都不再更新，界面上也没有任何提醒。
- **修法**：到官方 [google.com/chrome](https://www.google.com/chrome/) 下载安装包，直接覆盖安装。书签、扩展和登录状态都会保留，更新程序也会一起重装。
- 如果 `chrome://policy` 里有更新相关的策略，说明更新是被单位或其它软件管着的。
- **为什么重要**：旧浏览器缺安全补丁，也缺媒体栈的修复。有些脚本管理器功能（比如 Chrome 138 起需要的「允许运行用户脚本」开关）也要求较新的浏览器版本。

## 4. 编码：播放策略怎么选

位置：播放器 ⚙ →「更多播放设置」→「播放策略」。界面可能随 B 站版本变化。它保存在本地存储 `bilibili_player_codec_prefer_type` 里：`0` 默认、`1` HEVC、`2` AVC、`3` AV1。

| 你的情况 | 建议 | 理由 |
|---|---|---|
| 硬件加速正常，`chrome://gpu` 有 `Decode hevc main` | **HEVC** | 码率比 AVC 低很多；在 Chrome 里 HEVC 一定走硬件，不会意外变成软解 |
| 还有 `Decode av1 profile main`（大致是较新的显卡和核显，比如 NVIDIA RTX 30 系及以后，见 [NVIDIA 解码支持表](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new)） | **AV1** 或 HEVC | AV1 码率最低。但 Chrome 总会报告 AV1“可播放”（内置 dav1d 软解），所以一定要以 `chrome://gpu` 为准 |
| 硬件加速修不好 | **AVC**（临时） | 软解 AVC 最轻；但码率最高，冷门视频会更依赖网络 |

**不要为了“保险”默认切到 AVC。** 在 BiliLoader 列出的样本里，同画质下 AVC 的码率是 HEVC 的 2.3–2.7 倍：

| 清晰度 | AVC | HEVC | AV1 | 来源 |
|---|---:|---:|---:|---|
| 1080P | 4.5 Mbps | 1.9 Mbps | ≈2.1 Mbps | [BiliLoader](https://github.com/Phantivia/BiliLoader)；AV1 来自 [BTR #45](https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues/45) |
| 1080P 60 帧 | 9.9 Mbps | 3.7 Mbps | 3.5 Mbps | [BiliLoader](https://github.com/Phantivia/BiliLoader) |
| 4K | ≈16.5 Mbps | ≈12 Mbps | ≈9 Mbps | [V2EX t/1106060](https://v2ex.com/t/1106060) |

码率因视频而异。比如荷兰案例第 3 轮的冷门视频是 1080P60 AVC，声明码率只有 3.48 Mbps。

说明：
- 选「默认」时播放器怎么挑编码，目前只有第三方说法（据说是 AV1 > HEVC > AVC），没有 B 站官方来源，所以**明确选一个**更可控。
- 低播放量的视频可能没有 HEVC 或 AV1 版本（未验证），以「视频统计信息」里实际的 Mime Type 为准。

## 5. 其它本地因素

| 因素 | 什么时候该怀疑 | 怎么办 |
|---|---|---|
| 节能模式 / 电池 | 笔记本没插电，或电量很低 | 插上电源；关闭 `chrome://settings/performance` 里的「节能模式」；Windows 电源模式选「最佳性能」 |
| 混合显卡（集显 + 独显） | 想用某块显卡的特有功能（比如 NVIDIA RTX 视频超分 VSR） | 一般不用改，集显通常也能硬解。需要时到 Windows 设置 → 系统 → 屏幕 → 显示卡，把浏览器设为「高性能」 |
| 刷新率节奏 | 不丢帧，但画面“一顿一顿” | 144 Hz 改成 120 Hz 或 60 Hz 试试；G-SYNC 一次只对一个窗口生效（据 Blur Busters 的「G-SYNC 101」指南） |
| NVIDIA RTX 视频超分（VSR） | 开了 VSR 后掉帧 | 设成「自动」或关掉。NVIDIA 说明画质等级高于系统能力时可能卡顿 |
| 弹幕 | 关弹幕就好 | 降低弹幕密度；或用 [pakku.js](https://github.com/xmcp/pakku.js) 合并刷屏弹幕 |
| 扩展 / 脚本 | 访客窗口里就好 | 逐个停用扩展排查；加速脚本一次只开一个 |

## 6. 三分钟诊断流程

准备一个热门视频（比如 BV15KpR6TENe）和一个冷门视频（播放量很低、时长较长、你没看过的），两者用同一清晰度、同一播放策略。**这时还不要开任何加速脚本。**

| 步 | 用时 | 做什么 | 看什么 |
|---|---|---|---|
| 1 | 40 秒 | 热门、冷门各播 30 秒 | 只有冷门卡，是缓冲；两个都卡，是解码或渲染 |
| 2 | 30 秒 | 右键视频 →「视频统计信息」 | Mime Type 里的编码（`avc1` = H.264，`hev1` / `hvc1` = HEVC，`av01` = AV1）、Resolution、Video DataRate、Video Speed、Video Host、Dropped Frames |
| 3 | 30 秒 | 运行 [`decode-check.js`](../../tools/decode-check.js)，或者看 `chrome://gpu` | 硬件加速是否生效（§2） |
| 4 | 45 秒 | `chrome://media-internals` → Players → bilibili | `kIsPlatformVideoDecoder` = `true` 就是硬解 |
| 5 | 30 秒 | F12 → Network → 过滤框输入 `m4s` | Domain 是实际在用的节点；单个请求的 Waiting（TTFB）。冷门视频如果每段都要等 1–2 秒、吞吐又很低，就是 CDN 回源问题 |
| 6 | 30 秒 | 关弹幕；再开一个访客窗口播同一个冷门视频 | 关弹幕就好，是弹幕负担；只有访客窗口好，是某个扩展 |

**怎么判断**

| 现象 | 结论 |
|---|---|
| 转圈；音画一起停；Video Speed 低于约 1.5 倍 Video DataRate；Dropped Frames 不涨 | **缓冲（网络）** → [02](02-why-cdn.md) |
| 不转圈；声音继续、画面卡；缓冲条远远领先；Dropped Frames 持续上涨（超过 1%，或每秒好几帧） | **解码 / 渲染** → 按 §2–§5 修，修好就结束 |

想要客观记录数据，可以粘贴只读的 [`tools/play-monitor.js`](../../tools/play-monitor.js)。它会记录首帧时间、卡顿次数和时长、拖动后的等待、丢帧。

**检查点**：做完这些，你应该能写出这样一句话：“是缓冲：只有冷门卡，Video Speed 低于 DataRate，不丢帧，硬解正常。”或者“是解码：……”。

---

下一篇：[02 · 为什么只有冷门视频转圈](02-why-cdn.md)
