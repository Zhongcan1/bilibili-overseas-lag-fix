# 更新记录 · Changelog

## v1.0 · 2026-10-13

**首个公开版本 · First public release**

### 中文

- **新的核心结论**：海外 B 站卡顿通常来自两个独立原因。
  - **A. 本地播放链路**：浏览器硬件加速被关闭，导致软解和软件渲染。
  - **B. 冷门长尾内容**：海外 CDN 边缘节点没有缓存。
- **60 秒自查清单**，第 1 步是检查硬件加速。
- **荷兰案例**：3 轮测速，覆盖 3 个冷门视频和 1 个热门视频、10 个 CDN 节点，其中一轮是登录后的 1080P60。还记录了案例中硬件加速被关闭的完整证据：SwiftShader、`mediaCapabilities`、只下发 AVC 轨道。
- **文档**（`docs/zh-CN/`）：01 诊断、02 原因与实测、03 BTR 安全审计（只覆盖提交 `0302b34`）、04 替代方案（已按事实核查更正）、05 安全安装 BTR（Tampermonkey / Violentmonkey 钉版本配方、A/B 测试、卸载）。
- **工具**（`tools/`，只读）：`cdn-bench.js`（CDN 冷数据测速）、`play-monitor.js`（播放监视）、新增 `decode-check.js`（硬件解码与渲染检查，不发网络请求）。
- **许可**：代码 MIT，文档 CC BY 4.0。

### English

- **New headline finding**: Bilibili stutter outside China usually has two independent causes.
  - **A. Local playback stack**: hardware acceleration is turned off in the browser, so decoding and rendering fall back to software.
  - **B. Cold long-tail content**: overseas CDN edges have nothing cached for it.
- **60-second checklist**, with hardware acceleration as step 1.
- **Netherlands case study**: three benchmark runs covering 3 cold videos, 1 hot video and 10 CDN nodes, one of them logged in at 1080P60. It also records the full evidence that hardware acceleration was off: SwiftShader, `mediaCapabilities`, and AVC-only tracks.
- **Docs** (`docs/en/`): 01 diagnosis, 02 why-cdn, 03 BTR security audit (commit `0302b34` only), 04 alternatives (with fact-check corrections), 05 safe install (pinned Tampermonkey / Violentmonkey recipe, A/B protocol, uninstall).
- **Tools** (`tools/`, read-only): `cdn-bench.js` (cold-cache CDN benchmark), `play-monitor.js` (playback monitor), and the new `decode-check.js` (hardware decode and rendering check, no network).
- **License**: code MIT, docs CC BY 4.0.

## 下次复查 · Next review

- [ ] BTR 发布新版本后，复审新提交，并更新 `docs/*/03` 和 README 里的“审计对象”。
      When BTR ships a new release, re-audit it and update the audited commit in `docs/*/03` and the README.
- [ ] 在不同时段、不同地区复测，把数据补进 `docs/*/02`（欢迎贡献）。
      Re-run benchmarks at other times and in other regions, and add the results to `docs/*/02` (contributions welcome).
- [ ] MBGTEB 的 Thread Ripper 模块有了实际使用反馈后，重新评估（`docs/*/04`）。
      Re-evaluate the MBGTEB Thread Ripper module once real-world reports exist (`docs/*/04`).
- [ ] 2026-11 中旬左右，全面复查一次链接和数据。
      Around mid-November 2026, re-check all links and figures.
