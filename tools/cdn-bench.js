/*
 * cdn-bench.js — B 站视频 CDN 只读测速 / read-only Bilibili video-CDN speed test
 * Chrome DevTools 控制台片段 / Chrome DevTools console snippet · v1.1 · 2026-10-13 · MIT License
 *
 * 粘贴前请先读完本文件和 tools/README.md。陌生人发来的控制台代码一律不要粘贴。
 * Read this whole file and tools/README.en.md before pasting it. Never paste console code from strangers.
 *
 * 用法 / Usage
 *  1. 测"基线"前：在脚本管理器里停用所有 B 站加速脚本（BTR / MBGTEB / realzza 等），VPN / WARP / 代理保持关闭。
 *     For a baseline: disable every Bilibili speed-up userscript (BTR, MBGTEB, realzza, ...) and keep VPN / WARP /
 *     proxies off.
 *  2. 打开 https://www.bilibili.com/video/BV… ，按 F5 刷新（站内跳转后 __playinfo__ 不会更新），
 *     画面出来后立刻暂停（空格）。最好登录，清晰度用你平时看的那一档。
 *     Open https://www.bilibili.com/video/BV… and press F5 (in-site navigation does not update __playinfo__);
 *     pause (Space) as soon as the picture appears. Preferably log in and use the quality you normally watch.
 *  3. F12 → Console → 粘贴整段 → 回车（第一次粘贴，Chrome 会要求先输入 allow pasting / 允许粘贴）。
 *     F12 → Console → paste the whole file → Enter (the first time, Chrome asks you to type "allow pasting").
 *  4. 等 1–6 分钟，看表格和"结论提示"。结果对象在 window.__cdnBench（不含签名地址，可 copy() 出来）。
 *     Wait 1–6 minutes, then read the table and the "verdict" line. The result object is window.__cdnBench
 *     (it contains no signed URLs; copy(JSON.stringify(__cdnBench)) copies it to the clipboard).
 *
 * 它做什么（只读）/ What it does (read-only)
 *  - 读 window.__playinfo__，找出当前清晰度的视频轨（优先用页面已请求过的 .m4s 路径来匹配）。
 *    Reads window.__playinfo__ and finds the video track being played (preferring .m4s paths the page requested).
 *  - 对"B 站分配的主/备节点"和下面 CFG 里的海外/大陆 upos 节点，各做 1 次单连接（SINGLE_MB）
 *    + 1 次 PAR 路并行（合计 PAR_MB）的 Range 下载，记录吞吐（Mbps）和首字节时间（TTFB）。
 *    For the primary/backup nodes Bilibili assigned, plus the overseas/mainland upos nodes in CFG below, it runs one
 *    single-connection Range download (SINGLE_MB) and one PAR-way parallel download (PAR_MB in total), and records
 *    throughput (Mbps) and time to first byte (TTFB).
 *  - 非 Akamai 节点：把一个非 Akamai 的签名地址换主机名复用；Akamai 只测它自己的签名地址
 *    （Akamai 地址换主机后能不能用，各项目说法相互矛盾，为免误判不拿它换）。
 *    Non-Akamai nodes reuse a non-Akamai signed URL with the host name swapped. Akamai is tested only with its own
 *    signed URL (projects disagree on whether Akamai URLs work on other hosts, so they are never swapped).
 *  - 每个节点、每次测试用文件中段（25%–90%）里不同的、随机错开的字节区间，尽量读"没人读过的冷数据"。
 *    Every node and every test reads a different, randomly offset byte range from the middle (25%–90%) of the
 *    file, to hit "cold" data that nobody has requested recently.
 *  - 样本总流量默认按节点数自动计算（约 40 MB；SINGLE_MB=8 时约 100 MB）；每个请求最多等 TIMEOUT_S 秒；
 *    节点若不支持 Range（返回 200）立刻中止。
 *    Total traffic is sized from the node count (about 40 MB; about 100 MB with SINGLE_MB=8). Each request waits at
 *    most TIMEOUT_S seconds; a node that ignores Range (HTTP 200) is aborted at once.
 * 它不做什么 / What it does NOT do
 *  - 不带 Cookie（credentials:'omit'）；只连 *.bilivideo.com / *.bilivideo.cn 和 B 站分配的 upos-*.akamaized.net。
 *    No cookies (credentials:'omit'); it only connects to *.bilivideo.com / *.bilivideo.cn and to the
 *    upos-*.akamaized.net host that Bilibili assigned.
 *  - 不调用 B 站 API，不改设置/存储，不上传任何东西；控制台里只打印主机名，不打印签名地址。
 *    No Bilibili API calls, no settings or storage changes, no uploads; the console shows host names only, never
 *    signed URLs (signed URLs contain your account id and IP address).
 *  - 为避开其它脚本改写过的 fetch，它临时插入一个隐藏的空白 iframe 借用原生 fetch，结束后移除。
 *    To avoid a fetch patched by other scripts, it borrows the native fetch from a temporary hidden blank iframe,
 *    which is removed at the end.
 * 局限（结果只作方向参考）/ Limits (results are indicative only)
 *  - 单次样本；重复测同一个视频会把数据"测热"；不同时段差异大（大陆晚高峰约为北京时间 19–23 点）。
 *    One sample per node; re-testing the same video "warms" it up; results vary with the time of day (the mainland
 *    evening peak is roughly 19:00–23:00 Beijing time, UTC+8).
 *  - 2 MB 样本在 200–330 ms RTT 上受 TCP 慢启动限制，大陆单连接数字偏低；可把 SINGLE_MB 改成 8 再测
 *    （BUDGET_MB 保持 0 即可，预算会自动放大到约 100 MB）。
 *    At a 200–330 ms RTT (e.g. Europe to mainland nodes) a 2 MB sample is limited by TCP slow start, so mainland
 *    single-connection numbers read low; set SINGLE_MB to 8 and re-test (keep BUDGET_MB at 0; it grows to ~100 MB).
 *  - 大陆节点走 HTTP/2：同一主机的并行请求共用一条 TCP 连接；hw/08c/08h 等同 IP 节点会合并连接，
 *    多个节点的并行速度不能简单相加。单连接测试先跑（含建连），并行复用连接，并行数字略偏乐观。
 *    Mainland nodes speak HTTP/2: parallel requests to one host share one TCP connection, and same-IP nodes
 *    (hw/08c/08h, ...) may share connections, so the parallel speeds of several nodes do not add up. The single test
 *    runs first (including connection setup) and the parallel test reuses the connection, so parallel numbers are
 *    slightly optimistic.
 *  - "结论提示"按当前视频轨的码率判断；未登录时往往只有 360P/480P，码率很低，结论会偏乐观——
 *    请登录后用常看的清晰度测，或设 CFG.TARGET_MBPS（例如 6 ≈ 1080P+）。
 *    The verdict compares against the current track's bitrate. Logged out you often get only 360P/480P, whose low
 *    bitrate makes the verdict too optimistic: log in and use your usual quality, or set CFG.TARGET_MBPS
 *    (e.g. 6 ≈ 1080P+).
 *
 * 输出里保留的中文值（逻辑未改，所以仍是中文）/ Chinese values kept in the output (logic unchanged):
 *   类型 role: 分配-主 = assigned primary · 分配-备 = assigned backup · 海外 = overseas · 大陆 = mainland ·
 *              额外 = extra (CFG.EXTRA)
 *   备注 note: 超时 = timeout · 中止 = aborted · 网络错误 = network error · Range不符 = Content-Range mismatch ·
 *              多余数据 = more bytes than requested · HTTP 416 超出文件末尾 = past the end of the file ·
 *              超出流量预算，跳过 = skipped (over BUDGET_MB) · 单连: / 并行: = single: / parallel:
 */
(async () => {
  'use strict';
  // 可调参数 / settings you may edit
  const CFG = {
    OVERSEAS: ['upos-sz-mirroraliov.bilivideo.com', 'upos-sz-mirrorcosov.bilivideo.com', 'cn-hk-eq-01-01.bilivideo.com'],
    MAINLAND: ['upos-sz-mirrorali.bilivideo.com', 'upos-sz-mirrorhw.bilivideo.com', 'upos-sz-mirror08c.bilivideo.com',
      'upos-sz-mirrorcos.bilivideo.com', 'upos-sz-mirrorbd.bilivideo.com', 'upos-sz-estgoss.bilivideo.com'],
    EXTRA: [],        // 想多测的节点，例如 'upos-sz-mirrorhwo1.bilivideo.com'（只接受 *.bilivideo.com）
                      // extra nodes to test, e.g. 'upos-sz-mirrorhwo1.bilivideo.com' (*.bilivideo.com only)
    SINGLE_MB: 2,     // 单连接样本大小（MB）/ single-connection sample size (MB)
    PAR: 8,           // 并行路数 / number of parallel requests
    PAR_MB: 2,        // 并行样本合计大小（MB，平均分给 PAR 路）/ total parallel sample (MB, split across PAR)
    BUDGET_MB: 0,     // 0 = 自动（按节点数 × (SINGLE_MB+PAR_MB) 加 4 MB 余量）；填数字 = 手动上限，超出的节点会被跳过
                      // 0 = auto (nodes × (SINGLE_MB+PAR_MB) + 4 MB); a number = hard cap, later nodes are skipped
    TIMEOUT_S: 15,    // 每个请求的超时（秒）/ per-request timeout (seconds)
    QN: 0,            // 指定清晰度 id（如 80 = 1080P）；0 = 自动取当前在播的那一条
                      // force a quality id (e.g. 80 = 1080P); 0 = the track currently playing
    TARGET_MBPS: 0    // "结论提示"按多少 Mbps 码率来判断；0 = 用当前视频轨的码率。未登录/低清晰度时可填 6（≈1080P+）
                      // bitrate (Mbps) the verdict is judged against; 0 = current track; use 6 (≈1080P+) if logged out
  };
  const MiB = 1048576, ALIGN = 65536;
  const BILI = /(^|\.)bilivideo\.(com|cn)$/i, AKAM = /^upos-[a-z0-9-]+\.akamaized\.net$/i;
  const say = (...a) => console.log('%c[cdn-bench]', 'color:#fb7299;font-weight:bold', ...a);
  const host = (u) => { try { return new URL(u).hostname; } catch { return ''; } };
  const path = (u) => { try { return new URL(u).pathname; } catch { return ''; } };
  const allowed = (u) => /^https:\/\//i.test(u) && (BILI.test(host(u)) || AKAM.test(host(u)));

  // ---- 1. 找到当前视频轨 / find the current video track ----
  if (!/^(www|m)\.bilibili\.com$/i.test(location.hostname)) return void say('请在 www.bilibili.com 的视频页上运行。 / Run this on a www.bilibili.com video page.');
  const pi = window.__playinfo__;
  const dash = pi?.data?.dash || pi?.result?.dash || pi?.data?.result?.video_info?.dash || pi?.result?.video_info?.dash;
  if (!dash?.video?.length) {
    return void say('没找到 window.__playinfo__ 里的 DASH 视频信息。请在 /video/BV… 页面按 F5 刷新，等画面出来后暂停，再运行。' +
      '（番剧、付费或地区受限的页面可能没有这项数据。） / No DASH video info in window.__playinfo__. Press F5 on a /video/BV… page, pause once the picture appears, then run again (bangumi, paid or region-restricted pages may not have this data).');
  }
  const urlOf = (r) => r.baseUrl || r.base_url || '';
  const seen = performance.getEntriesByType('resource').map((e) => path(e.name)).filter((p) => p.endsWith('.m4s')).reverse();
  let rep = CFG.QN ? dash.video.find((r) => r.id === CFG.QN) : null;
  for (const p of seen) { if (rep) break; rep = dash.video.find((r) => path(urlOf(r)) === p); }
  if (!rep) {
    let pref; try { pref = { 1: 12, 2: 7, 3: 13 }[localStorage.getItem('bilibili_player_codec_prefer_type')]; } catch { /* 读不到就算了 / ignore if unreadable */ }
    const q = pi?.data?.quality ?? pi?.result?.quality;
    rep = dash.video.find((r) => r.id === q && r.codecid === pref) || dash.video.find((r) => r.id === q) || dash.video[0];
  }
  const codec = { 7: 'AVC', 12: 'HEVC', 13: 'AV1' }[rep.codecid] || String(rep.codecs || '?');
  const st = window.__INITIAL_STATE__ || {};
  const part = Number(new URLSearchParams(location.search).get('p')) || 1;
  const cid = st.videoData?.pages?.[part - 1]?.cid || st.videoData?.cid || st.cid;
  if (cid && !path(urlOf(rep)).includes(String(cid))) say('⚠ __playinfo__ 似乎不属于当前视频（站内跳转后它不会更新），建议按 F5 刷新后重跑。 / __playinfo__ seems to belong to another video (in-site navigation does not update it); press F5 and run again.');
  let deadline = 0; try { deadline = Number(new URL(urlOf(rep)).searchParams.get('deadline')) || 0; } catch { /* 无 / none */ }
  if (deadline && deadline * 1000 < Date.now()) return void say('签名地址已过期（页面打开太久了），请按 F5 刷新后重跑。 / The signed URLs have expired (the page has been open too long); press F5 and run again.');
  const vid = document.querySelector('video');
  if (vid && !vid.paused) say('⚠ 视频正在播放，会和测速抢带宽；建议先暂停（空格）再重跑。 / The video is playing and competes for bandwidth; pause it (Space) and run again.');
  if (document.documentElement.hasAttribute('data-btr-userscript')) say('⚠ 检测到 BTR 正在运行：测"基线"前请先在脚本管理器里停用它。 / BTR detected: for a baseline, disable it in your userscript manager first.');

  // ---- 2. 组装要测的节点 / build the list of nodes ----
  const originals = [urlOf(rep), ...(rep.backupUrl || rep.backup_url || [])].filter(allowed);
  if (!originals.length) return void say('当前视频轨没有可测的 B 站视频节点地址，停止。 / The current track has no testable Bilibili CDN URL; stopping.');
  const donor = originals.find((u) => !AKAM.test(host(u)));
  const rows = [];
  const add = (h, role, url) => { if (!rows.some((r) => r.host === h)) rows.push({ host: h, role, url }); };
  originals.forEach((u, i) => add(host(u), i ? '分配-备' : '分配-主', u));
  const swap = (h) => { const u = new URL(donor); u.hostname = h; u.port = ''; return u.href; };
  if (!donor) say('只拿到 Akamai 地址：它的签名换到别的主机上不一定被接受，为免误判，只测分配的节点。 / Only Akamai URLs are available: their signature may not be accepted by other hosts, so only the assigned nodes are tested.');
  else {
    for (const [role, list] of [['海外', CFG.OVERSEAS], ['大陆', CFG.MAINLAND], ['额外', CFG.EXTRA]]) {
      for (const h of list) {
        if (/^[a-z0-9.-]+\.bilivideo\.com$/i.test(h)) add(h, role, swap(h)); else say('忽略（不是 *.bilivideo.com）/ ignored (not *.bilivideo.com):', h);
      }
    }
  }

  // ---- 3. 借一个没被页面脚本改写过的 fetch / borrow a fetch that no page script has patched ----
  const ifr = document.createElement('iframe');
  ifr.style.display = 'none';
  document.documentElement.appendChild(ifr);
  const W = ifr.contentWindow;
  const nfetch = W.fetch.bind(W);
  const init = (signal, range) => ({ headers: { Range: range }, credentials: 'omit', cache: 'no-store', mode: 'cors',
    referrer: location.href, referrerPolicy: 'strict-origin-when-cross-origin', signal });

  async function get(url, a, b) {
    if (!allowed(url)) throw new Error('不允许的主机 / host not allowed: ' + host(url)); // 双保险：只连 B 站视频节点 / second guard: Bilibili video hosts only
    const ac = new W.AbortController(), t0 = performance.now();
    let ttfb = 0, bytes = 0, note = '';
    const timer = setTimeout(() => { note = note || '超时'; ac.abort(); }, CFG.TIMEOUT_S * 1000);
    try {
      const res = await nfetch(url, init(ac.signal, `bytes=${a}-${b}`));
      ttfb = performance.now() - t0;
      if (res.status !== 206) { note = res.status === 416 ? 'HTTP 416 超出文件末尾' : 'HTTP ' + res.status; ac.abort(); } else {
        const cr = res.headers.get('content-range') || '';
        if (cr && !cr.startsWith(`bytes ${a}-`)) note = 'Range不符';
        const reader = res.body.getReader();
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          bytes += value.length;
          if (bytes > b - a + 1) { note = '多余数据'; ac.abort(); break; }
        }
      }
    } catch (e) { note = note || (e?.name === 'AbortError' ? '中止' : '网络错误'); }
    clearTimeout(timer);
    return { bytes, ttfb, ms: performance.now() - t0, note };
  }

  try {
    // ---- 4. 文件大小 → 规划互不重叠的中段区间 / file size → plan non-overlapping mid-file ranges ----
    let size = 0;
    for (const u of [...originals, ...rows.filter((r) => r.role === '大陆').map((r) => r.url)].slice(0, 4)) {
      const ac = new W.AbortController(), t = setTimeout(() => ac.abort(), 8000);
      try {
        const r = await nfetch(u, init(ac.signal, 'bytes=0-0'));
        size = Number((r.headers.get('content-range') || '').split('/')[1]) || 0;
      } catch { /* 换下一个地址再试 / try the next URL */ }
      clearTimeout(t); ac.abort();
      if (size) break;
    }
    if (!size) {
      size = Math.floor((dash.duration || 0) * (rep.bandwidth || 0) / 8 * 0.8);
      say('⚠ 读不到文件大小，按 码率×时长×0.8 估算；若个别请求报 HTTP 416（超出文件末尾）属正常。 / Could not read the file size; estimating it as bitrate × duration × 0.8. An occasional HTTP 416 (past the end of the file) is then normal.');
    }
    if (size < 8 * MiB) return void say(`文件太小或拿不到大小（≈${(size / MiB).toFixed(1)} MB），测出来没有意义：请换更长的视频或更高的清晰度。 / File too small or its size is unknown, so the test would be meaningless: try a longer video or a higher quality.`);
    const slot = size * 0.65 / (rows.length * 2), lo = size * 0.25;
    const fit = (mb) => Math.max(256 * 1024, Math.min(mb * MiB, Math.floor(slot * 0.9 / ALIGN) * ALIGN));
    const L1 = fit(CFG.SINGLE_MB), L2 = fit(CFG.PAR_MB);
    const piece = Math.max(ALIGN, Math.floor(L2 / CFG.PAR / ALIGN) * ALIGN), npar = Math.max(1, Math.min(CFG.PAR, Math.floor(L2 / piece)));
    if (L1 < CFG.SINGLE_MB * MiB || L2 < CFG.PAR_MB * MiB) say(`文件偏小：样本缩小为 单连 ${(L1 / MiB).toFixed(2)} MB · 并行 ${(L2 / MiB).toFixed(2)} MB，噪声会更大。 / Small file: samples reduced to the single · parallel sizes shown; results will be noisier.`);
    const at = (k, len) => Math.ceil((lo + k * slot + Math.random() * Math.max(0, slot - len - ALIGN)) / ALIGN) * ALIGN;

    // ---- 5. 逐个节点测：先单连接，再并行 / test each node: single connection first, then parallel ----
    const mbps = (B, ms) => (B && ms > 0 ? +(B * 8 / 1000 / ms).toFixed(1) : 0);
    const perNode = L1 + npar * piece;
    // BUDGET_MB = 0：按节点数自动放大，保证每个节点都测到；填了数字才是硬上限
    // BUDGET_MB = 0: sized from the node count so every node is tested; only a number is a hard cap
    let left = CFG.BUDGET_MB > 0 ? CFG.BUDGET_MB * MiB : perNode * rows.length + 4 * MiB;
    const planMB = Math.min(left / MiB, perNode * rows.length / MiB).toFixed(0);
    say(`开始 / start：${rows.length} 个节点 nodes，每个 each：单连 single ${(L1 / MiB).toFixed(2)} MB + 并行 parallel ${npar}×${Math.round(piece / 1024)} KB，合计最多约 total ≤ ~${planMB} MB。`);
    if (perNode * rows.length > left) say(`⚠ BUDGET_MB=${CFG.BUDGET_MB} 不够测完 ${rows.length} 个节点，排在后面的会被跳过；改回 0（自动）或调大后重跑。 / BUDGET_MB is too small for all nodes: the later ones will be skipped; set it back to 0 (auto) or raise it, then run again.`);
    for (const [i, r] of rows.entries()) {
      if (left < perNode) { r.skip = '超出流量预算，跳过'; continue; }
      left -= perNode;
      const s0 = at(2 * i, L1);
      r.s = await get(r.url, s0, s0 + L1 - 1);
      const p0 = at(2 * i + 1, npar * piece), t0 = performance.now();
      const ps = await Promise.all(Array.from({ length: npar }, (_, j) => get(r.url, p0 + j * piece, p0 + (j + 1) * piece - 1)));
      r.sM = mbps(r.s.bytes, r.s.ms);
      r.pM = mbps(ps.reduce((x, y) => x + y.bytes, 0), performance.now() - t0);
      r.pT = Math.max(0, ...ps.map((x) => x.ttfb));
      r.pNote = [...new Set(ps.map((x) => x.note).filter(Boolean))].join('/');
      say(`${r.host}（${r.role}）：单连 single ${r.sM} Mbps · 并行 parallel ${r.pM} Mbps`);
      await new Promise((res) => setTimeout(res, 400));
    }

    // ---- 6. 输出 / output ----
    const trackR = (rep.bandwidth || 0) / 1e6;
    const tgt = Number(CFG.TARGET_MBPS) || 0;
    const R = tgt > 0 ? tgt : trackR, need = 1.5 * R;
    const ms = (x) => (x ? Math.round(x) : '—'), ratio = (x) => (R && x ? +(x / R).toFixed(1) : '—');
    console.table(rows.map((r) => ({
      '节点 node': r.host, '类型 role': r.role, '单连 single Mbps': r.sM ?? '—', '单连 single TTFB ms': ms(r.s?.ttfb),
      [`并行 parallel×${npar} Mbps`]: r.pM ?? '—', '并行最慢 slowest parallel TTFB ms': ms(r.pT),
      '单连÷码率 single÷bitrate': ratio(r.sM), '并行÷码率 parallel÷bitrate': ratio(r.pM),
      '备注 note': r.skip || [r.s?.note && '单连:' + r.s.note, r.pNote && '并行:' + r.pNote].filter(Boolean).join(' ')
    })));
    const best = (pred, key) => Math.max(0, ...rows.filter(pred).map((r) => r[key] || 0));
    const A = rows.find((r) => r.role === '分配-主')?.sM || 0;
    const SW = best((r) => /mirror(ali|hw|cos|aliov|cosov)\./.test(r.host), 'sM');
    // 并行按线路归类：B 站分配的节点按主机名归入大陆或海外（BTR 海外模式也会用分配的 Akamai / cosov 地址）
    // parallel results by route: assigned nodes count as mainland or overseas by host name
    // (BTR's overseas mode also uses the assigned Akamai / cosov URLs)
    const isML = (r) => r.role === '大陆' || (r.role.startsWith('分配') && CFG.MAINLAND.includes(r.host));
    const isOV = (r) => r.role === '海外' || (r.role.startsWith('分配') && (AKAM.test(r.host) || CFG.OVERSEAS.includes(r.host)));
    const MP = best(isML, 'pM'), OP = best(isOV, 'pM');
    say(`视频轨 track：qn ${rep.id} · ${codec} · ${rep.width}×${rep.height} · 码率 bitrate ${trackR.toFixed(2)} Mbps · 文件约 file ≈ ${(size / MiB).toFixed(0)} MB`);
    if (tgt > 0) say(`下面按 CFG.TARGET_MBPS = ${R} Mbps 判断（不是当前视频轨的码率）。 / The verdict below uses this CFG.TARGET_MBPS, not the current track's bitrate.`);
    else if (trackR && trackR < 2) say(`⚠ 当前视频轨码率只有 ${trackR.toFixed(2)} Mbps（多半是未登录或清晰度很低），下面的结论只对这一档成立。` +
      '想知道 1080P+ 够不够：登录后切到常看的清晰度、F5 后重跑，或把 CFG.TARGET_MBPS 设成 6 再跑。 / This track is below 2 Mbps (probably logged out or a very low quality), so the verdict holds for this quality only. To judge 1080P+: log in, pick your usual quality, press F5 and rerun, or set CFG.TARGET_MBPS to 6.');
    say(`分配主节点单连 assigned primary, single ${A} · 换源池最佳单连 best switch-pool node, single ${SW} · 大陆最佳并行 best mainland, parallel ${MP} · 海外最佳并行 best overseas, parallel ${OP}（Mbps）`);
    let verdict = '大陆、海外节点加上并行都不到 1.5× 码率 → 降清晰度、用 HEVC/AV1（需硬件解码），或用官方客户端离线缓存。 / Neither mainland nor overseas nodes reach 1.5× the bitrate, even in parallel → lower the quality, use HEVC/AV1 (if hardware-decoded), or use the official app\'s offline cache.';
    if (!R) verdict = '拿不到码率，只能看绝对值。 / Bitrate unknown: judge by the absolute numbers.';
    else if (A >= need) verdict = 'B 站分配的主节点单连接已 ≥1.5× 码率（这个视频对你是"热"的）→ 卡顿多半不是 CDN，回到诊断（硬件加速、解码）。 / The node Bilibili assigned already gives ≥1.5× the bitrate on one connection (this video is "hot" for you) → the stutter is probably not the CDN; go back to diagnosis (hardware acceleration, decoding).';
    else if (!donor) verdict = '分配节点不够快，但只拿到 Akamai 地址、测不了别的节点 → F5 刷新换一批地址，或换个视频再测。 / The assigned nodes are too slow, but only Akamai URLs were available, so no other node could be tested → press F5 for fresh URLs, or try another video.';
    else if (SW >= need) verdict = '换个节点、单连接就 ≥1.5× 码率 → 单连接换源脚本（如 realzza）可能就够；BTR 也行。 / Another node reaches ≥1.5× the bitrate on a single connection → a single-connection CDN-switch userscript (e.g. realzza) may be enough; BTR is also an option.';
    else if (MP >= need) verdict = '"大陆 + 并行"能到 1.5× 码率 / mainland + parallel reaches 1.5× the bitrate' + (OP >= need ? '（"海外 + 并行"也能 / so does overseas + parallel）' : '') + ' → BTR、MBGTEB Thread Ripper 这类多连接方案对你有意义 / multi-connection tools such as BTR or MBGTEB Thread Ripper are worth an A/B test.';
    else if (OP >= need) verdict = '只有"海外 + 并行"能到 1.5× 码率 → BTR 海外模式、MBGTEB Thread Ripper 这类方案对你有意义。 / Only overseas + parallel reaches 1.5× the bitrate → BTR\'s overseas mode or MBGTEB Thread Ripper are worth an A/B test.';
    say('结论提示 / verdict: ' + verdict);
    say('单次样本，只作方向参考。冷测请换没看过的视频，或换个时段重测。 / One sample only, indicative. For a cold test use a video you have not watched, or retest at another time of day.');
    window.__cdnBench = { at: new Date().toISOString(), qn: rep.id, codec, mbps: +trackR.toFixed(3), targetMbps: +R.toFixed(3), sizeMB: +(size / MiB).toFixed(1),
      rows: rows.map(({ url, ...r }) => r) };
    return window.__cdnBench;
  } finally {
    ifr.remove();
  }
})();
