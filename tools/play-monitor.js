/*
 * play-monitor.js — 只读播放监视器 / read-only playback monitor
 * Chrome DevTools 控制台片段，不发任何网络请求 / Chrome DevTools console snippet, makes no network requests
 * v1 · 2026-10-13 · MIT License
 *
 * 粘贴前请先读完本文件。陌生人发来的控制台代码一律不要粘贴。
 * Read this whole file before pasting it. Never paste console code from strangers.
 *
 * 用途：A/B 测试时客观记录 首帧时间、卡顿次数与时长、拖动后的等待、前方缓冲、丢帧。
 * Purpose: objective numbers for A/B tests: startup time, stall count and duration, waits after seeking, forward
 * buffer and dropped frames.
 * 用法 / Usage
 *  1. 播放器里关掉「自动开播」，按 F5 刷新视频页，先不要点播放。
 *     Turn off the player's autoplay, press F5 on the video page, and do not press play yet.
 *  2. F12 → Console → 粘贴本段 → 回车；然后点播放，正常看 3 分钟（可以按计划拖动进度）。
 *     F12 → Console → paste this file → Enter; then press play and watch normally for 3 minutes (seek as planned).
 *  3. 每 10 秒打印一行；结束时在控制台输入 __pm.stop()，会打印汇总表（也存在 __pm.summary）。
 *     It prints one line every 10 s; type __pm.stop() when done to print the summary table (also in __pm.summary).
 * 它只读 <video> 的状态和事件：不改页面、不改设置、不发请求。
 * It only reads the <video> element's state and events: no page changes, no settings changes, no requests.
 * BTR（按审计的提交 0302b34）接管播放时仍使用页面原有的 <video>，所以理论上同样适用（未实测）。
 * BTR (at the audited commit 0302b34) keeps using the page's own <video> when it takes over playback, so this
 * should work with it as well (not tested).
 * 局限：站内跳转到别的视频后 <video> 可能被替换，请每个视频重新粘贴一次；B 站的 WASM 播放器 <bwp-video> 不支持。
 * Limits: in-site navigation may replace the <video>, so paste again for every video; Bilibili's WASM player
 * <bwp-video> is not supported.
 *
 * 汇总表列名（逻辑未改，所以仍是中文）/ Summary columns (logic unchanged, so they stay in Chinese):
 *   观察秒数 = seconds observed · 首帧 ms = startup time, play → playing (ms) · 卡顿次数（不含拖动）= stalls,
 *   seeks excluded · 卡顿总秒 = total stall time (s) · 拖动后等待次数 = waits after seeking ·
 *   拖动等待总秒 = total wait after seeking (s) · 当前前方缓冲 s = forward buffer now (s) ·
 *   最小前方缓冲 s = minimum forward buffer (s) · 丢帧/总帧 = dropped / total frames · 丢帧率 % = dropped frames (%)
 */
(() => {
  const tag = '[play-monitor]';
  const v = document.querySelector('video');
  if (!v) { console.warn(tag, '没找到 <video>（可能是 WASM 播放器 <bwp-video>），无法监视。 / No <video> found (maybe the WASM player <bwp-video>); cannot monitor.'); return; }
  if (window.__pm?.stop) window.__pm.stop(true);
  const now = () => performance.now();
  const S = { start: now(), playAt: 0, firstFrameMs: null, stalls: 0, stallMs: 0, seekWaits: 0, seekMs: 0,
    waitAt: 0, waitSeek: false, minAhead: Infinity, dropped0: 0, total0: 0 };
  const quality = () => (v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : { droppedVideoFrames: 0, totalVideoFrames: 0 });
  const q0 = quality(); S.dropped0 = q0.droppedVideoFrames; S.total0 = q0.totalVideoFrames;
  const ahead = () => {
    const b = v.buffered;
    for (let i = 0; i < b.length; i++) if (b.start(i) <= v.currentTime + 0.1 && v.currentTime < b.end(i)) return b.end(i) - v.currentTime;
    return 0;
  };
  const endWait = () => {
    if (!S.waitAt) return;
    const d = now() - S.waitAt;
    if (S.waitSeek) S.seekMs += d; else S.stallMs += d;
    S.waitAt = 0;
  };
  const handlers = {
    play: () => { if (!S.playAt) S.playAt = now(); },
    playing: () => { if (S.firstFrameMs === null && S.playAt) S.firstFrameMs = Math.round(now() - S.playAt); endWait(); },
    waiting: () => {
      if (S.firstFrameMs === null || S.waitAt) return; // 起播前的等待算进首帧时间 / waits before the first frame count as startup time
      S.waitAt = now(); S.waitSeek = v.seeking;
      if (S.waitSeek) S.seekWaits += 1; else S.stalls += 1;
    },
    pause: endWait
  };
  for (const [e, f] of Object.entries(handlers)) v.addEventListener(e, f);
  if (!v.paused) console.warn(tag, '视频已经在播放：首帧时间测不到，其余照常记录。（要测首帧：关自动开播 → 刷新 → 先粘贴再点播放） / The video is already playing: startup time cannot be measured, everything else is recorded. (To measure it: turn autoplay off → F5 → paste first, then press play.)');

  const snapshot = () => {
    const q = quality(), a = ahead();
    if (S.firstFrameMs !== null) S.minAhead = Math.min(S.minAhead, a);
    const dropped = q.droppedVideoFrames - S.dropped0, total = q.totalVideoFrames - S.total0;
    return {
      '观察秒数': Math.round((now() - S.start) / 1000),
      '首帧 ms': S.firstFrameMs ?? '—',
      '卡顿次数（不含拖动）': S.stalls,
      '卡顿总秒': +((S.stallMs + (S.waitAt && !S.waitSeek ? now() - S.waitAt : 0)) / 1000).toFixed(1),
      '拖动后等待次数': S.seekWaits,
      '拖动等待总秒': +((S.seekMs + (S.waitAt && S.waitSeek ? now() - S.waitAt : 0)) / 1000).toFixed(1),
      '当前前方缓冲 s': +a.toFixed(1),
      '最小前方缓冲 s': S.minAhead === Infinity ? '—' : +S.minAhead.toFixed(1),
      '丢帧/总帧': `${dropped} / ${total}`,
      '丢帧率 %': total ? +(dropped * 100 / total).toFixed(2) : 0
    };
  };
  const timer = setInterval(() => {
    const s = snapshot();
    console.log(tag, `缓冲 buffer ${s['当前前方缓冲 s']}s · 卡顿 stalls ${s['卡顿次数（不含拖动）']} 次 times / ${s['卡顿总秒']}s · 丢帧 dropped ${s['丢帧/总帧']}`);
  }, 10000);
  window.__pm = {
    stop(silent) {
      clearInterval(timer);
      for (const [e, f] of Object.entries(handlers)) v.removeEventListener(e, f);
      this.summary = snapshot();
      if (!silent) console.table([this.summary]);
      return this.summary;
    }
  };
  console.log(tag, '已开始：点播放后正常观看，结束时输入 __pm.stop() / Started: press play and watch normally; type __pm.stop() when done.');
})();
