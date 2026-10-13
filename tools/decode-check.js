/*
 * decode-check.js — 只读的硬件加速 / 解码自查 / read-only hardware-acceleration & decoding check
 * Chrome / Edge DevTools 控制台片段，不发任何网络请求 / DevTools console snippet, makes no network requests
 * v1 · 2026-10-13 · MIT License
 * 粘贴前请先读完本文件。陌生人发来的控制台代码一律不要粘贴。
 * Read this whole file before pasting it. Never paste console code from strangers.
 *
 * 用法 / Usage: 打开 www.bilibili.com 任意页面 → F12 → Console → 粘贴 → 回车，几秒内出结果。
 *   Open any www.bilibili.com page → F12 → Console → paste → Enter; results appear within seconds.
 *   在别的网站也能跑，只是读不到 B 站播放器的编码设置。/ It also runs elsewhere, minus the Bilibili codec setting.
 * 它做什么 / What it does
 *  - 读 WebGL 渲染器名称：SwiftShader 等软件渲染器、或者根本没有 WebGL，通常说明"使用图形加速功能"被关了或 GPU 被禁用。
 *    Reads the WebGL renderer: a software renderer such as SwiftShader, or no WebGL at all, usually means
 *    "Use graphics acceleration when available" is off or the GPU is blocklisted.
 *  - 用 navigator.mediaCapabilities.decodingInfo 询问 AVC / HEVC / AV1 在 1080p60 和 4K60 下能否解码（supported）、
 *    是否流畅（smooth）、是否省电（powerEfficient；在 Chrome 里为 true 通常表示有硬件解码）。
 *    Asks navigator.mediaCapabilities.decodingInfo whether AVC / HEVC / AV1 at 1080p60 and 4K60 are supported,
 *    smooth and powerEfficient (in Chrome, powerEfficient = true usually means a hardware decoder is used).
 *  - 读 B 站播放器的编码偏好 localStorage 'bilibili_player_codec_prefer_type'（0 默认 · 1 HEVC · 2 AVC · 3 AV1）。
 *    Reads the Bilibili player's codec preference from localStorage (0 default · 1 HEVC · 2 AVC · 3 AV1).
 * 它不做什么 / What it does NOT do: 不发请求、不改设置或存储、不读 Cookie。/ No requests, no setting or storage
 *   changes, no cookies.
 * 局限 / Limits: 这是浏览器的"能力声明"，不是实测；smooth 部分取决于本机过去的播放统计。请以 chrome://gpu 的
 *   "Video Decode: Hardware accelerated" 和 play-monitor.js 的丢帧为准。输出里有显卡型号，公开分享前可删掉。
 *   These are the browser's own capability claims, not measurements; smooth partly depends on past playback stats.
 *   Confirm with chrome://gpu ("Video Decode: Hardware accelerated") and play-monitor.js dropped frames. The output
 *   includes your GPU model; redact it before sharing publicly.
 */
(async () => {
  'use strict';
  const say = (...a) => console.log('%c[decode-check]', 'color:#00a1d6;font-weight:bold', ...a);
  const verdict = [];
  const tell = (zh, en) => { verdict.push(`${zh} / ${en}`); say(`${zh} / ${en}`); };

  // ---- 1. 浏览器版本 / browser version ----
  const brands = (navigator.userAgentData?.brands || []).filter((b) => !/not.?a.?brand/i.test(b.brand));
  const browser = brands.map((b) => `${b.brand} ${b.version}`).join(', ') || navigator.userAgent;
  say(`浏览器 / browser: ${browser}`);
  say('是否最新：打开 chrome://settings/help（Edge：edge://settings/help）；报错或一直卡住 → 从官网重新安装（保留个人资料）。 / ' +
    'Up to date? Open chrome://settings/help (Edge: edge://settings/help); if it errors or hangs, reinstall from the official site (your profile is kept).');

  // ---- 2. WebGL 渲染器 / WebGL renderer ----
  let renderer = '', webgl = false;
  try {
    const gl = document.createElement('canvas').getContext('webgl'); // 不插入页面 / never attached to the page
    if (gl) {
      webgl = true;
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      renderer = String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || '');
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  } catch { /* 无 WebGL / no WebGL */ }
  const softGL = !webgl || /swiftshader|llvmpipe|softpipe|basic render/i.test(renderer);
  say(`WebGL 渲染器 / renderer: ${webgl ? renderer || '?' : '不可用 / unavailable'}${softGL ? '  ⚠ 软件渲染 / software rendering' : ''}`);

  // ---- 3. 解码能力 / decoding capabilities ----
  const CODECS = { AVC: ['avc1.640032', 'avc1.640034'], HEVC: ['hev1.1.6.L123.90', 'hev1.1.6.L153.90'], AV1: ['av01.0.09M.08', 'av01.0.13M.08'] };
  const SIZES = [['1080p60', 1920, 1080, 6e6], ['4K60', 3840, 2160, 20e6]];
  const mc = navigator.mediaCapabilities, rows = [];
  if (!mc) say('⚠ 没有 navigator.mediaCapabilities，跳过解码检查 / navigator.mediaCapabilities is missing; decode check skipped');
  for (const [codec, strings] of Object.entries(mc ? CODECS : {})) {
    for (const [k, [fmt, width, height, bitrate]] of SIZES.entries()) {
      let r = { supported: false, smooth: false, powerEfficient: false };
      try {
        r = await mc.decodingInfo({ type: 'media-source',
          video: { contentType: `video/mp4; codecs="${strings[k]}"`, width, height, bitrate, framerate: 60 } });
      } catch { /* 浏览器拒绝此查询 = 不支持 / query rejected = unsupported */ }
      rows.push({ codec, fmt, supported: !!r.supported, smooth: !!r.smooth, powerEfficient: !!r.powerEfficient });
    }
  }
  if (rows.length) console.table(rows.map((r) => ({ '编码 codec': r.codec, '规格 format': r.fmt, '能解码 supported': r.supported,
    '流畅 smooth': r.smooth, '省电≈硬解 powerEfficient': r.powerEfficient })));
  const at1080 = (c, key) => rows.some((r) => r.codec === c && r.fmt === '1080p60' && r[key]);
  const HW = { AVC: at1080('AVC', 'powerEfficient'), HEVC: at1080('HEVC', 'powerEfficient'), AV1: at1080('AV1', 'powerEfficient') };
  const anyHW = HW.AVC || HW.HEVC || HW.AV1;

  // ---- 4. B 站播放策略 / Bilibili codec setting ----
  const onBili = /(^|\.)bilibili\.com$/i.test(location.hostname);
  let pref = null;
  try { pref = localStorage.getItem('bilibili_player_codec_prefer_type'); } catch { /* 读不到 / unreadable */ }
  const cur = { 1: 'HEVC', 2: 'AVC', 3: 'AV1' }[pref] || '';
  const prefName = !onBili ? '?（不在 bilibili.com / not on bilibili.com）' : cur || (pref && pref !== '0' ? `? (${pref})` : '默认 default');
  say(`B 站播放策略 / Bilibili codec setting: ${prefName}`);

  // ---- 5. 结论 / verdict ----
  if (softGL) tell('⚠ 浏览器在用软件渲染（SwiftShader 等）或没有 WebGL：多半是"使用图形加速功能（如果可用）"被关了，或 GPU 被禁用。' +
    '打开它：chrome://settings/system（Edge：edge://settings/system）→ 重新启动浏览器 → 再跑一次',
  '⚠ The browser renders in software (SwiftShader etc.) or has no WebGL: most likely "Use graphics acceleration when available" ' +
    'is off or the GPU is blocklisted. Turn it on at chrome://settings/system (Edge: edge://settings/system) → Relaunch → run this again');
  if (mc && !anyHW) tell('⚠ 1080p60 下 AVC / HEVC / AV1 都没有报告硬件解码（powerEfficient=false）：CPU 软解 1080P60 加弹幕，网速再快也可能卡。' +
    '修好后到 chrome://gpu 确认 "Video Decode: Hardware accelerated"',
  '⚠ No codec reports hardware decoding at 1080p60 (powerEfficient=false): software-decoding 1080P60 plus danmaku can ' +
    'stutter however fast the network is. After fixing, confirm "Video Decode: Hardware accelerated" in chrome://gpu');
  if (mc) {
    const good = ['HEVC', 'AV1'].filter((c) => HW[c]);
    const want = good.length ? good : ['AVC'];
    if (!anyHW) tell('修好之前：播放策略选 AVC（软解时最省 CPU），清晰度用 1080P（不要 60 帧）或更低',
      'Until then: set the codec to AVC (lightest for software decoding) and use 1080P (not 60 fps) or lower');
    else if (good.length) tell(`建议播放策略：${want.join(' 或 ')}（有硬解；同画质下码率通常比 AVC 低，对海外网络更友好）`,
      `Suggested codec: ${want.join(' or ')} (hardware-decoded; usually a lower bitrate than AVC at the same quality)`);
    else tell('建议播放策略：AVC（这里只有 AVC 是硬解）', 'Suggested codec: AVC (the only hardware-decoded one here)');
    if (onBili && cur && want.includes(cur)) tell('当前设置已符合建议', 'Your current setting already matches');
    else if (onBili) {
      const av1Soft = !cur && at1080('AV1', 'supported') && !HW.AV1;
      tell(`当前是 ${prefName}${av1Soft ? '（默认档在浏览器报告能播 AV1 时可能选 AV1，而这里 AV1 不是硬解）' : ''}` +
        ` → 播放器 ⚙ →「更多播放设置」→「播放策略」选 ${want[0]}，然后刷新页面`,
      `Current: ${prefName}${av1Soft ? ' ("default" may pick AV1 when the browser reports it playable, and AV1 is not hardware-decoded here)' : ''}` +
        ` → player ⚙ → 更多播放设置 (more settings) → 播放策略 (codec): pick ${want[0]}, then reload the page`);
    }
  }
  if (!softGL && anyHW) tell('✓ 硬件加速看起来正常。如果还卡，下一步用 cdn-bench.js 测网络 / CDN',
    '✓ Hardware acceleration looks fine. If it still stutters, test the network / CDN next with cdn-bench.js');
  window.__decodeCheck = { at: new Date().toISOString(), browser, webgl: { available: webgl, renderer, software: softGL },
    codecPref: pref, decoding: rows, verdict };
  say('结果在 window.__decodeCheck（含显卡型号，公开分享前可删掉） / Result in window.__decodeCheck (includes your GPU model; redact before sharing)');
  return window.__decodeCheck;
})();
