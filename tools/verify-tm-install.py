#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-tm-install.py

只读校验：Tampermonkey 里装的「Bilibili 线程撕裂者」(BTR) 是否与审计过的提交 0302b34
逐字节一致、文件头是否按 docs/zh-CN/05-safe-install.md 改好、自动更新是否已关闭。

Read-only check: is the "Bilibili 线程撕裂者" (BTR) userscript installed in Tampermonkey
byte-identical to the audited commit 0302b34, is its header edited as described in
docs/en/05-safe-install.md, and are its updates switched off?

  * Python 3.8+, standard library only; Windows / macOS / Linux.
  * Reads Tampermonkey's extension storage (a LevelDB folder) in a Chromium-based
    browser profile (Chrome / Edge / Brave / Chromium / Opera). Every file is opened
    read-only (shared read on Windows) and copied into memory. Nothing is written to
    disk, nothing is sent over the network, nothing is downloaded.
  * Prints only data about the matched script. Other scripts, their settings and
    their stored values are never printed. Script IDs and local paths are not printed.

Usage:
  python verify-tm-install.py                      # scan all profiles of all known browsers
  python verify-tm-install.py --browser chrome --profile "Default"
  python verify-tm-install.py --profile-dir "<a browser profile folder>"
  python verify-tm-install.py --storage-dir "<a copy of the extension's LevelDB folder>"
  python verify-tm-install.py --self-test          # test the built-in LevelDB/Snappy readers

Exit code: 0 = PASS, 1 = FAIL, 2 = nothing found / error.
Docs: tools/README.md (中文), tools/README.en.md (English). MIT License, see ../LICENSE.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import struct
import sys

TOOL_VERSION = "1.0"

# --------------------------------------------------------------------------------------
# What was audited (docs/*/03-btr-security-audit.md). Nothing here is fetched at run time.
# --------------------------------------------------------------------------------------
AUDITED_COMMIT = "0302b345cdfe367ac599b52dc6874e3f7967e220"
AUDITED_VERSION = "2026.10.8.1"
AUDITED_FILE_SHA256 = "7766622730f6d24febb89cd3669ff0c384997c260c652668082d84af61724dd9"
AUDITED_FILE_BYTES = 405714
# SHA-256 of the UTF-8 text that follows the first "// ==/UserScript==" marker in the
# audited file (LF line endings): the code Tampermonkey runs, without the header that
# the guide tells you to edit.
AUDITED_BODY_SHA256 = "793c4bc8e9803009bb9e0692e41fd856ad626b8a4ad2874b4ef8bad2fae1f74c"
AUDITED_BODY_BYTES = 404509
AUDITED_HEADER = [
    "// ==UserScript==",
    "// @name         Bilibili 线程撕裂者",
    "// @namespace    https://github.com/MrTangLuyao/Bilibili-thread-ripper",
    "// @version      2026.10.8.1",
    "// @description  保留哔哩哔哩原生播放器，通过多 CDN、多 Range 并发下载改善视频缓冲速度。",
    "// @icon         https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/main/icons/icon-128.png",
    "// @author       MrTangLuyao",
    "// @license      MIT",
    "// @homepageURL  https://github.com/MrTangLuyao/Bilibili-thread-ripper",
    "// @supportURL   https://github.com/MrTangLuyao/Bilibili-thread-ripper/issues",
    "// @updateURL    https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/main/user_scripts/bilibili-thread-ripper.user.js",
    "// @downloadURL  https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/main/user_scripts/bilibili-thread-ripper.user.js",
    "// @match        https://*.bilibili.com/*",
    "// @run-at       document-start",
    "// @grant        GM_registerMenuCommand",
    "// @grant        GM_addElement",
    "// @grant        unsafeWindow",
    "// @grant        GM.getValue",
    "// @grant        GM.setValue",
    "// @grant        GM_addValueChangeListener",
    "// @sandbox      JavaScript",
    "// @inject-into  content",
    "// ==/UserScript==",
]
BTR_NAMESPACE = "https://github.com/MrTangLuyao/Bilibili-thread-ripper"
DEFAULT_NAME = "线程撕裂者"
EXPECTED_MATCH = ["https://*.bilibili.com/*"]
EXPECTED_GRANTS = ["GM_registerMenuCommand", "GM_addElement", "unsafeWindow",
                   "GM.getValue", "GM.setValue", "GM_addValueChangeListener"]
EXPECTED_EXCLUDES = ["https://passport.bilibili.com/*", "https://pay.bilibili.com/*",
                     "https://account.bilibili.com/*", "https://member.bilibili.com/*"]
FORBIDDEN_KEYS = ("require", "resource", "connect", "include")
START_MARK = "// ==UserScript=="
END_MARK = "// ==/UserScript=="

# Official Tampermonkey extension IDs (Tampermonkey FAQ Q406).
KNOWN_EXTENSIONS = {
    "dhdgffkkebhmkfjojejmpbldmpobfkfo": ("Tampermonkey", "Chrome Web Store", False),
    "iikmkjmpaadaobahmlepeloendndfphd": ("Tampermonkey", "Microsoft Edge Add-ons", False),
    "mfdhdgbonjidekjkjmjaneanmdmpmidf": ("Tampermonkey", "Opera add-ons", False),
    "gcalenpjmijncebpfijmoaglllgpjagf": ("Tampermonkey BETA", "Chrome Web Store", True),
    "fcmfnpggmnlmfebfghbfnillijihnkoh": ("Tampermonkey BETA", "Microsoft Edge Add-ons", True),
    "lcmhijbkigalmkeommnijlpobloojgfn": ("Tampermonkey Legacy", "Chrome Web Store", False),
}

LANG = "both"


def out(zh, en, indent=""):
    """Print one message in the selected language(s)."""
    if LANG in ("zh", "both"):
        print(indent + zh)
    if LANG in ("en", "both") and (LANG == "en" or en != zh):
        print(indent + en)


# --------------------------------------------------------------------------------------
# Low-level readers: CRC32C, Snappy, LevelDB log / table / MANIFEST. Every read is bounds
# checked; malformed input raises CorruptError and is skipped and counted, never trusted.
# --------------------------------------------------------------------------------------
class CorruptError(Exception):
    pass


class UnsupportedError(Exception):
    pass


def _make_crc_table():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0x82F63B78 if c & 1 else c >> 1
        table.append(c)
    return table


_CRC_TABLE = _make_crc_table()


def crc32c(data, crc=0):
    crc ^= 0xFFFFFFFF
    t = _CRC_TABLE
    for b in data:
        crc = t[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def crc_unmask(masked):
    rot = (masked - 0xA282EAD8) & 0xFFFFFFFF
    return ((rot >> 17) | (rot << 15)) & 0xFFFFFFFF


def get_varint(buf, pos, limit=None):
    limit = len(buf) if limit is None else limit
    result = shift = 0
    while True:
        if pos >= limit or shift > 63:
            raise CorruptError("bad varint")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def get_lp(buf, pos, limit=None):
    """Length-prefixed slice."""
    limit = len(buf) if limit is None else limit
    n, pos = get_varint(buf, pos, limit)
    if pos + n > limit:
        raise CorruptError("slice past end")
    return buf[pos:pos + n], pos + n


def snappy_decompress(src, max_len=1 << 28):
    """Raw Snappy block format (what LevelDB uses), pure Python, bounds checked."""
    n, p = get_varint(src, 0)
    if n > max_len:
        raise CorruptError("snappy length too large")
    out_buf = bytearray()
    size = len(src)
    while p < size:
        tag = src[p]
        p += 1
        kind = tag & 3
        if kind == 0:                              # literal
            ln = tag >> 2
            if ln >= 60:
                nb = ln - 59
                if p + nb > size:
                    raise CorruptError("snappy literal header")
                ln = int.from_bytes(src[p:p + nb], "little")
                p += nb
            ln += 1
            if p + ln > size or len(out_buf) + ln > n:
                raise CorruptError("snappy literal")
            out_buf += src[p:p + ln]
            p += ln
            continue
        if kind == 1:                              # copy, 1-byte offset
            if p + 1 > size:
                raise CorruptError("snappy copy1")
            ln = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | src[p]
            p += 1
        elif kind == 2:                            # copy, 2-byte offset
            if p + 2 > size:
                raise CorruptError("snappy copy2")
            ln = (tag >> 2) + 1
            off = src[p] | (src[p + 1] << 8)
            p += 2
        else:                                      # copy, 4-byte offset
            if p + 4 > size:
                raise CorruptError("snappy copy4")
            ln = (tag >> 2) + 1
            off = int.from_bytes(src[p:p + 4], "little")
            p += 4
        if off == 0 or off > len(out_buf) or len(out_buf) + ln > n:
            raise CorruptError("snappy copy out of range")
        start = len(out_buf) - off
        if off >= ln:
            out_buf += out_buf[start:start + ln]
        else:                                      # overlapping copy repeats the pattern
            chunk = bytes(out_buf[start:])
            reps, rem = divmod(ln, off)
            out_buf += chunk * reps + chunk[:rem]
    if len(out_buf) != n:
        raise CorruptError("snappy length mismatch")
    return bytes(out_buf)


LOG_BLOCK = 32768
LOG_HEADER = 7          # crc32c (4, masked) + length (2) + type (1)
FULL, FIRST, MIDDLE, LAST = 1, 2, 3, 4


def iter_log_records(data, stats):
    """Logical records of a LevelDB log file (.log / MANIFEST): 32 KiB blocks, each
    physical record = 7-byte header + payload, FULL or FIRST/MIDDLE.../LAST fragments.
    Records with a bad checksum or broken fragment chain are dropped and counted."""
    pos, n = 0, len(data)
    frags = None
    while pos < n:
        left = LOG_BLOCK - pos % LOG_BLOCK
        if left < LOG_HEADER:                      # block trailer, zero filled
            pos += left
            continue
        if pos + LOG_HEADER > n:
            break                                  # torn tail (file still being written)
        masked, length, rtype = struct.unpack_from("<IHB", data, pos)
        if rtype == 0 and length == 0:             # zero / preallocated area: skip block
            pos += left
            continue
        end = pos + LOG_HEADER + length
        if end > n:
            stats["torn"] += 1                     # incomplete last record
            break
        if LOG_HEADER + length > left:
            stats["bad"] += 1
            frags = None
            pos += left
            continue
        payload = data[pos + LOG_HEADER:end]
        if crc_unmask(masked) != crc32c(payload, crc32c(bytes([rtype]))):
            stats["bad"] += 1                      # LevelDB drops the rest of the block
            frags = None
            pos += left
            continue
        pos = end
        if rtype == FULL:
            if frags is not None:
                stats["bad"] += 1
            frags = None
            stats["records"] += 1
            yield payload
        elif rtype == FIRST:
            if frags is not None:
                stats["bad"] += 1
            frags = [payload]
        elif rtype == MIDDLE:
            if frags is None:
                stats["bad"] += 1
            else:
                frags.append(payload)
        elif rtype == LAST:
            if frags is None:
                stats["bad"] += 1
            else:
                frags.append(payload)
                stats["records"] += 1
                yield b"".join(frags)
            frags = None
        else:
            stats["bad"] += 1
            frags = None
    if frags is not None:
        stats["torn"] += 1


def iter_write_batch(rec):
    """WriteBatch: seq (u64) + count (u32), then per entry: tag 1 = put(key, value),
    tag 0 = delete(key); keys and values are varint length prefixed."""
    if len(rec) < 12:
        raise CorruptError("short batch")
    seq, count = struct.unpack_from("<QI", rec, 0)
    p = 12
    for i in range(count):
        if p >= len(rec):
            raise CorruptError("batch count")
        tag = rec[p]
        p += 1
        key, p = get_lp(rec, p)
        if tag == 1:
            val, p = get_lp(rec, p)
            yield seq + i, key, val
        elif tag == 0:
            yield seq + i, key, None
        else:
            raise CorruptError("batch tag")


def read_table_block(data, offset, size, stats):
    if offset + size + 5 > len(data):
        raise CorruptError("block handle past end")
    btype = data[offset + size]
    masked = struct.unpack_from("<I", data, offset + size + 1)[0]
    if crc_unmask(masked) != crc32c(data[offset:offset + size + 1]):
        raise CorruptError("block checksum")
    raw = data[offset:offset + size]
    if btype == 0:
        return raw
    if btype == 1:
        return snappy_decompress(raw)
    stats["unsupported"] += 1
    raise UnsupportedError("compression type %d" % btype)


def iter_block_entries(block):
    if len(block) < 4:
        raise CorruptError("short block")
    nrestarts = struct.unpack_from("<I", block, len(block) - 4)[0]
    limit = len(block) - 4 - 4 * nrestarts
    if limit < 0:
        raise CorruptError("restart array")
    p, prev = 0, b""
    while p < limit:
        shared, p = get_varint(block, p, limit)
        non_shared, p = get_varint(block, p, limit)
        vlen, p = get_varint(block, p, limit)
        if shared > len(prev) or p + non_shared + vlen > limit:
            raise CorruptError("block entry")
        key = prev[:shared] + block[p:p + non_shared]
        p += non_shared
        yield key, block[p:p + vlen]
        p += vlen
        prev = key


def iter_table(data, stats):
    """Entries of a LevelDB table (.ldb / .sst): footer -> index block -> data blocks.
    Internal key = user key + 8-byte (sequence << 8 | type); type 1 = value, 0 = deletion."""
    if len(data) < 48 or struct.unpack_from("<Q", data, len(data) - 8)[0] != 0xDB4775248B80FB57:
        raise CorruptError("not a LevelDB table")
    footer = data[-48:]
    _, p = get_varint(footer, 0)
    _, p = get_varint(footer, p)
    index_off, p = get_varint(footer, p)
    index_size, p = get_varint(footer, p)
    index = read_table_block(data, index_off, index_size, stats)
    for _, handle in iter_block_entries(index):
        stats["blocks"] += 1
        try:
            off, q = get_varint(handle, 0)
            size, q = get_varint(handle, q)
            block = read_table_block(data, off, size, stats)
            for ikey, val in iter_block_entries(block):
                if len(ikey) < 8:
                    raise CorruptError("internal key")
                tag = struct.unpack_from("<Q", ikey, len(ikey) - 8)[0]
                kind = tag & 0xFF
                if kind not in (0, 1):
                    raise CorruptError("value type")
                yield tag >> 8, ikey[:-8], (val if kind == 1 else None)
        except (CorruptError, UnsupportedError):
            stats["bad_blocks"] += 1


def parse_manifest(data):
    """Returns (log_number, prev_log_number, live table numbers) from a MANIFEST."""
    stats = {"records": 0, "bad": 0, "torn": 0}
    log_number, prev_log = None, 0
    live = set()
    for rec in iter_log_records(data, stats):
        p, deleted, added = 0, [], []
        while p < len(rec):
            tag, p = get_varint(rec, p)
            if tag == 1:                                   # comparator
                _, p = get_lp(rec, p)
            elif tag == 2:                                 # log number
                log_number, p = get_varint(rec, p)
            elif tag in (3, 4):                            # next file / last sequence
                _, p = get_varint(rec, p)
            elif tag == 5:                                 # compact pointer
                _, p = get_varint(rec, p)
                _, p = get_lp(rec, p)
            elif tag == 6:                                 # deleted file
                level, p = get_varint(rec, p)
                num, p = get_varint(rec, p)
                deleted.append((level, num))
            elif tag == 7:                                 # new file
                level, p = get_varint(rec, p)
                num, p = get_varint(rec, p)
                _, p = get_varint(rec, p)
                _, p = get_lp(rec, p)
                _, p = get_lp(rec, p)
                added.append((level, num))
            elif tag == 9:                                 # previous log number
                prev_log, p = get_varint(rec, p)
            else:
                raise CorruptError("manifest tag %d" % tag)
        for item in deleted:
            live.discard(item)
        for item in added:
            live.add(item)
    if log_number is None:
        raise CorruptError("manifest without log number")
    return log_number, prev_log, {num for _, num in live}


# --------------------------------------------------------------------------------------
# Reading the storage folder (read-only snapshot into memory)
# --------------------------------------------------------------------------------------
DB_FILE_RE = re.compile(r"^(\d+)\.(log|ldb|sst)$")


def read_shared(path):
    """Read a whole file without blocking the browser: on Windows open it with
    FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE and GENERIC_READ only."""
    if os.name == "nt":
        try:
            import ctypes
            import msvcrt
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                        wintypes.HANDLE]
            k32.CreateFileW.restype = wintypes.HANDLE
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = k32.CreateFileW(path, 0x80000000, 0x7, None, 3, 0x80, None)
            if handle is None or handle == wintypes.HANDLE(-1).value:
                raise OSError(ctypes.get_last_error(), "cannot open (locked?)", path)
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
            except OSError:
                k32.CloseHandle(handle)
                raise
            with os.fdopen(fd, "rb") as f:
                return f.read()
        except OSError:
            raise
        except Exception:                                  # ctypes unavailable: plain open
            pass
    with open(path, "rb") as f:
        return f.read()


def list_db_files(folder):
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n for n in names
                  if DB_FILE_RE.match(n) or n == "CURRENT" or n.startswith("MANIFEST-"))


def snapshot(folder, warnings):
    """Copy the LevelDB files into memory. Retries if the folder changes while reading
    (for example a compaction in the running browser)."""
    files = {}
    for _attempt in range(3):
        before = list_db_files(folder)
        files, skipped = {}, []
        for name in before:
            try:
                files[name] = read_shared(os.path.join(folder, name))
            except OSError:
                skipped.append(name)
        if list_db_files(folder) == before:
            for name in skipped:
                warnings.append(("跳过了无法读取（被锁定？）的文件 %s" % name,
                                 "Skipped a file that could not be read (locked?): %s" % name))
            return files
    warnings.append(("读取过程中存储一直在变化，结果可能不完整；请稍后重跑，或先关闭浏览器。",
                     "The storage kept changing while it was read; results may be incomplete. "
                     "Re-run, or close the browser first."))
    return files


def load_latest(folder, warnings, info):
    """Latest value of every key that contains '@source#' or '@meta#' (highest sequence
    number wins across logs and tables; a deletion wins if it is the newest)."""
    files = snapshot(folder, warnings)
    logs, tables = [], []
    for name in files:
        m = DB_FILE_RE.match(name)
        if m:
            (logs if m.group(2) == "log" else tables).append((int(m.group(1)), name))
    live_logs, live_tables = logs, tables
    manifest_ok = False
    current = files.get("CURRENT", b"").decode("ascii", "replace").strip()
    if current and current in files:
        try:
            log_no, prev_log, live = parse_manifest(files[current])
            live_logs = [(n, f) for n, f in logs if n >= log_no or (prev_log and n == prev_log)]
            live_tables = [(n, f) for n, f in tables if n in live]
            missing = live - {n for n, _ in tables}
            if missing:
                warnings.append(("MANIFEST 里列出的 %d 个表文件没读到；请重跑。" % len(missing),
                                 "%d table file(s) listed in MANIFEST were not read; re-run." % len(missing)))
            manifest_ok = True
        except CorruptError:
            pass
    if not manifest_ok:
        warnings.append(("无法解析 MANIFEST，改为读取全部 .log / .ldb 文件。",
                         "Could not parse MANIFEST; reading every .log / .ldb file instead."))
    latest = {}
    wanted = (b"@source#", b"@meta#")

    def consider(seq, key, val):
        if (wanted[0] in key or wanted[1] in key) and (key not in latest or seq >= latest[key][0]):
            latest[key] = (seq, val)

    lstats = {"records": 0, "bad": 0, "torn": 0}
    for _, name in sorted(live_logs):
        for rec in iter_log_records(files[name], lstats):
            try:
                for seq, key, val in iter_write_batch(rec):
                    consider(seq, key, val)
            except CorruptError:
                lstats["bad"] += 1
    tstats = {"blocks": 0, "bad_blocks": 0, "unsupported": 0}
    for _, name in sorted(live_tables):
        try:
            for seq, key, val in iter_table(files[name], tstats):
                consider(seq, key, val)
        except (CorruptError, UnsupportedError):
            tstats["bad_blocks"] += 1
    info.update(logs=len(live_logs), tables=len(live_tables), manifest=manifest_ok,
                log_records=lstats["records"], log_bad=lstats["bad"], log_torn=lstats["torn"],
                blocks=tstats["blocks"], bad_blocks=tstats["bad_blocks"],
                unsupported=tstats["unsupported"])
    if lstats["bad"] or tstats["bad_blocks"]:
        warnings.append(("跳过了 %d 条损坏的日志记录、%d 个损坏或无法解压的表数据块（浏览器正在写入时可能出现）。"
                         % (lstats["bad"], tstats["bad_blocks"]),
                         "Skipped %d corrupt log record(s) and %d corrupt or undecodable table block(s) "
                         "(can happen while the browser is writing)." % (lstats["bad"], tstats["bad_blocks"])))
    if tstats["unsupported"]:
        warnings.append(("有 %d 个表数据块使用了本工具不支持的压缩格式；如果没找到脚本，请在 Tampermonkey 里对这个脚本"
                         "做一次改动（比如关掉再打开），让最新记录写进 .log 后重跑。" % tstats["unsupported"],
                         "%d table block(s) use a compression this tool does not support. If the script is not "
                         "found, change something on it in Tampermonkey (e.g. disable and re-enable it) so the "
                         "latest record lands in the .log, then re-run." % tstats["unsupported"]))
    return latest


def json_value(raw):
    obj = json.loads(raw.decode("utf-8"))
    if isinstance(obj, dict) and "value" in obj:
        return obj["value"]
    return obj


# --------------------------------------------------------------------------------------
# Userscript header helpers
# --------------------------------------------------------------------------------------
META_LINE_RE = re.compile(r"^\s*//\s*@([\w:.\-]+)(?:\s+(.*?))?\s*$")


def split_source(src):
    s, e = src.find(START_MARK), src.find(END_MARK)
    if s < 0 or e < 0 or e < s:
        return None
    return src[:s], src[s:e + len(END_MARK)], src[e + len(END_MARK):]


def header_lines(header):
    return [line.rstrip("\r") for line in header.split("\n")]


def parse_header(lines):
    return [(m.group(1), (m.group(2) or "").strip(), line)
            for line in lines for m in [META_LINE_RE.match(line)] if m]


def norm(line):
    return " ".join(line.split())


def describe_url(url):
    """(zh, en) description of a URL from Tampermonkey's record. Only well-known public
    URLs are shown in full; anything else is reduced to its host or hidden."""
    if not url:
        return "（空）", "(empty)"
    if url == "none":
        return "none", "none"
    if AUDITED_COMMIT in url:
        return "钉提交地址（0302b34）", "pinned commit URL (0302b34)"
    if url.startswith("https://raw.githubusercontent.com/MrTangLuyao/Bilibili-thread-ripper/main/"):
        return "…/main/…（跟随 main 分支）", "…/main/… (follows the main branch)"
    m = re.match(r"^https://([^/?#]+)", url)
    if m:
        return "https://%s/…（其他地址）" % m.group(1), "https://%s/… (other URL)" % m.group(1)
    return "（其他来源，不显示）", "(other source, not shown)"


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------
class Result:
    def __init__(self):
        self.items = []

    def add(self, status, zh, en, detail=None, fix=None):
        self.items.append((status, zh, en, detail, fix))

    @property
    def failed(self):
        return [i for i in self.items if i[0] == "FAIL"]

    def show(self):
        for status, zh, en, detail, fix in self.items:
            tag = "[%s]" % status
            pad = "  " + " " * (len(tag) + 1)
            if LANG in ("zh", "both"):
                print("  " + tag + " " + zh)
            if LANG == "en":
                print("  " + tag + " " + en)
            elif LANG == "both" and en != zh:
                print(pad + en)
            if detail:
                for d in detail if isinstance(detail, list) else [detail]:
                    print(pad + d)
            if fix and status == "FAIL":
                out("→ 修复：" + fix[0], "→ Fix: " + fix[1], pad)


def check_script(src, meta, audited_body):
    r = Result()
    parts = split_source(src)
    if parts is None:
        r.add("FAIL", "找不到 ==UserScript== 文件头", "No ==UserScript== header found")
        return r, None
    prefix, header, body = parts
    lines = header_lines(header)
    parsed = parse_header(lines)
    values = lambda key: [v for k, v, _ in parsed if k == key]
    options = (meta or {}).get("options") or {}
    override = options.get("override") or {}

    # 1. version
    ver = values("version")
    mver = (meta or {}).get("version")
    ok = ver == [AUDITED_VERSION] and (mver in (None, AUDITED_VERSION))
    r.add("PASS" if ok else "FAIL", "版本 %s" % (", ".join(ver) or "?"),
          "Version %s" % (", ".join(ver) or "?"),
          None if ok else "expected %s (Tampermonkey record: %s)" % (AUDITED_VERSION, mver),
          ("从钉提交地址重新安装（05 §2 ①）", "reinstall from the pinned commit URL (05 §2 ①)"))

    # 2. body
    body_bytes = body.encode("utf-8")
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    lf_sha = hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    detail = "sha256 %s…  %s bytes  (audited %s…  %s bytes)" % (
        body_sha[:16], format(len(body_bytes), ","), AUDITED_BODY_SHA256[:16], format(AUDITED_BODY_BYTES, ","))
    if body_sha == AUDITED_BODY_SHA256:
        r.add("PASS", "正文（实际运行的代码）与审计提交 0302b34 逐字节一致",
              "Body (the code that runs) is byte-identical to audited commit 0302b34", detail)
    elif lf_sha == AUDITED_BODY_SHA256:
        r.add("PASS", "正文与审计版本一致（只有换行符是 CRLF，不影响代码含义）",
              "Body matches the audited version (only the line endings are CRLF, which does not change the code)",
              detail)
    else:
        extra = [detail]
        if audited_body is not None:
            a, b = audited_body.split("\n"), body.replace("\r\n", "\n").split("\n")
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else "<EOF>"
                y = b[i] if i < len(b) else "<EOF>"
                if x != y:
                    line_no = i + 1 + len(lines) - 1
                    extra.append("first difference at line %d of the stored script:" % line_no)
                    extra.append("  audited:   " + x[:100])
                    extra.append("  installed: " + y[:100])
                    break
        else:
            extra.append("(run with --audited-file <saved pinned file> to locate the first difference)")
        r.add("FAIL", "正文与审计版本不一致", "Body differs from the audited version", extra,
              ("删除这个脚本，从钉提交地址重新安装（05 §2 ①–⑤）",
               "delete this script and reinstall from the pinned commit URL (05 §2 ①–⑤)"))

    # 3. nothing executable outside the body
    bad = []
    if prefix.strip("\ufeff \t\r\n"):
        bad.append("text before // ==UserScript==")
    for i, line in enumerate(lines, 1):
        if line.strip() and not line.lstrip().startswith("//"):
            bad.append("line %d is not a comment: %s" % (i, line[:100]))
    r.add("FAIL" if bad else "PASS", "文件头里只有注释行，文件头前没有代码" if not bad else "文件头之外还有代码",
          "Header holds only comment lines and nothing precedes it" if not bad else "Code outside the body",
          bad or None, ("删除后重新安装（05 §2）", "delete and reinstall (05 §2)"))

    # 4/5. @updateURL / @downloadURL none
    for key, step in (("updateURL", "③A"), ("downloadURL", "③A")):
        vals = values(key)
        ok = vals == ["none"]
        r.add("PASS" if ok else "FAIL", "@%s %s" % (key, " / ".join(vals) or "（缺失）"),
              "@%s %s" % (key, " / ".join(vals) or "(missing)"),
              None if ok else "expected exactly one line: // @%s none" % key,
              ("编辑器里把这一行改成 `// @%s none` 并保存（05 §2 %s）" % (key, step),
               "change this line to `// @%s none` in the editor and save (05 §2 %s)" % (key, step)))

    # 6. check_for_updates
    cfu = options.get("check_for_updates") if meta else None
    if cfu is False:
        r.add("PASS", "「检查更新」已关闭（options.check_for_updates = false）",
              '"Check for updates" is off (options.check_for_updates = false)')
    elif cfu is True:
        r.add("FAIL", "「检查更新」仍是勾选状态（options.check_for_updates = true）",
              '"Check for updates" is still ticked (options.check_for_updates = true)', None,
              ("脚本的「设置」标签页 → 取消勾选「检查更新」→ 保存（05 §2 ③B）",
               'script "Settings" tab → untick "Check for updates" → save (05 §2 ③B)'))
    else:
        r.add("FAIL", "读不到「检查更新」设置", 'Could not read the "Check for updates" setting',
              "no @meta record found for this script" if not meta else "options.check_for_updates missing",
              ("在 Tampermonkey 里打开这个脚本的「设置」并保存一次，然后重跑",
               "open the script's Settings in Tampermonkey, save once, then re-run"))

    # 7. the 4 excludes
    hdr_ex = values("exclude")
    user_ex = list(override.get("use_excludes") or [])
    keep_orig = override.get("merge_excludes", True) is not False
    where, missing = [], []
    for url in EXPECTED_EXCLUDES:
        if url in hdr_ex and keep_orig:
            where.append("header")
        elif url in user_ex:
            where.append("user excludes")
        else:
            missing.append(url)
    detail = []
    if missing:
        detail.append("missing: " + ", ".join(missing))
        if not keep_orig and any(u in hdr_ex for u in EXPECTED_EXCLUDES):
            detail.append("the header excludes are switched off in Tampermonkey (original excludes unticked)")
    else:
        detail.append("from: " + ", ".join(sorted(set(where))))
    r.add("FAIL" if missing else "PASS",
          "4 条敏感子域排除规则" + ("缺 %d 条" % len(missing) if missing else "都在"),
          "The 4 sensitive-subdomain excludes " + ("— %d missing" % len(missing) if missing else "are all present"),
          detail, ("按 05 §2 ④ 加上 4 条 @exclude（每条单独一行）", "add the 4 @exclude lines per 05 §2 ④, one per line"))

    # 8. @run-at document-start on its own line; no glued lines anywhere
    glued = [l for l in lines if len(re.findall(r"//\s*@", l)) > 1]
    runat = values("run-at")
    orig_run_at = override.get("orig_run_at")
    ok = runat == ["document-start"] and not glued and orig_run_at in (None, "document-start")
    detail = ["glued line: " + g[:120] for g in glued]
    if runat != ["document-start"]:
        detail.append("@run-at lines: %s" % (runat or "none"))
    r.add("PASS" if ok else "FAIL", "@run-at document-start 独占一行，没有粘连的行" if ok else "@run-at 行有问题或有粘连的行",
          "@run-at document-start is on its own line; no glued lines" if ok else "@run-at problem or glued lines",
          detail or None, ("在编辑器里把粘在一起的 `// @…` 拆成各占一行并保存（05 §2 ④ 的换行提示）",
                           "split the glued `// @…` directives onto separate lines and save (05 §2 ④ line-break note)"))
    if options.get("run_at") not in (None, "", "document-start"):
        r.add("WARN", "Tampermonkey 设置里覆盖了运行时机：%s" % options.get("run_at"),
              "Tampermonkey settings override the run-at time: %s" % options.get("run_at"))

    # 9. exactly the 6 expected @grant
    grants = values("grant")
    ok = sorted(grants) == sorted(EXPECTED_GRANTS)
    detail = None
    if not ok:
        extra = [g for g in grants if g not in EXPECTED_GRANTS]
        lack = [g for g in EXPECTED_GRANTS if g not in grants]
        detail = "extra: %s; missing: %s; count %d" % (extra or "-", lack or "-", len(grants))
    r.add("PASS" if ok else "FAIL", "@grant 正好是预期的 6 项" if ok else "@grant 与审计版本不同",
          "Exactly the 6 expected @grant" if ok else "@grant differs from the audited version", detail,
          ("不要使用这个版本；删除后从钉提交地址重新安装", "do not use this copy; delete and reinstall from the pinned URL"))

    # 10. no @require / @resource / @connect / @include; @match unchanged; no widening in TM settings
    found = ["@%s %s" % (k, v) for k, v, _ in parsed if k in FORBIDDEN_KEYS]
    if values("match") != EXPECTED_MATCH:
        found.append("@match %s" % values("match"))
    if meta:
        for field in ("requires", "resources", "connects"):
            if meta.get(field):
                found.append("Tampermonkey record '%s' is not empty" % field)
        for field in ("use_includes", "use_matches", "use_connects"):
            if override.get(field):
                found.append("user-added %s in Tampermonkey settings: %s" % (field[4:], override.get(field)))
    r.add("FAIL" if found else "PASS",
          "没有 @require / @resource / @connect / @include，匹配范围仍只有 https://*.bilibili.com/*"
          if not found else "多出了外部依赖或匹配范围",
          "No @require / @resource / @connect / @include; scope is still only https://*.bilibili.com/*"
          if not found else "Extra dependencies or a wider scope", found or None,
          ("删除多出来的规则；文件本身被改过就重新安装", "remove the extra rules; reinstall if the file itself was changed"))

    # 11. the rest of the header is unchanged
    skip = ("updateURL", "downloadURL", "exclude")
    got = [norm(l) for l in lines if not ((META_LINE_RE.match(l) or [None, None])[1] in skip)]
    exp = [norm(l) for l in AUDITED_HEADER if not ((META_LINE_RE.match(l) or [None, None])[1] in skip)]
    if got == exp:
        r.add("PASS", "文件头其余各行与审计版本一致（@sandbox、@inject-into、@namespace 等）",
              "Every other header line matches the audited version (@sandbox, @inject-into, @namespace, …)")
    else:
        added = [l for l in got if l not in exp]
        removed = [l for l in exp if l not in got]
        detail = ["+ " + l[:120] for l in added] + ["- " + l[:120] for l in removed]
        if not detail:
            detail = ["same lines, different order"]
        r.add("WARN" if not added and not removed else "FAIL",
              "文件头还有其他改动", "The header has other changes", detail,
              ("撤销这些改动，或删除后重新安装", "undo these changes, or delete and reinstall"))

    # Cross-check: Tampermonkey's parsed record vs the header
    if meta:
        diffs = []
        for field, header_vals in (("grant", grants), ("excludes", hdr_ex), ("matches", values("match"))):
            if field in meta and sorted(meta.get(field) or []) != sorted(header_vals):
                diffs.append(field)
        if diffs:
            r.add("WARN", "Tampermonkey 内部记录与文件头不一致：%s（在编辑器里保存一次后重跑）" % ", ".join(diffs),
                  "Tampermonkey's parsed record differs from the header: %s (save once in the editor, re-run)"
                  % ", ".join(diffs))

    # Information
    if meta:
        enabled = meta.get("enabled")
        r.add("INFO" if enabled else "WARN",
              "脚本状态：%s" % ("已启用" if enabled else "已停用（BTR 不会运行）"),
              "Script state: %s" % ("enabled" if enabled else "disabled (BTR will not run)"))
        up, dl, src_url = (describe_url(meta.get(k)) for k in ("updateURL", "downloadURL", "fileURL"))
        r.add("INFO", "Tampermonkey 内部记录的更新地址：updateURL = %s；downloadURL = %s" % (up[0], dl[0]),
              "Update URLs in Tampermonkey's record: updateURL = %s; downloadURL = %s" % (up[1], dl[1]),
              "(05 §2 ③B: Tampermonkey 5.5.1 kept the old downloadURL after the header edit; "
              "that is why the ③B switch is required)" if (meta.get("downloadURL") or "") not in ("", "none") else None)
        r.add("INFO", "安装来源：%s" % src_url[0], "Installed from: %s" % src_url[1])
        lm = meta.get("lastModified")
        if isinstance(lm, (int, float)) and lm > 0:
            when = datetime.datetime.fromtimestamp(lm / 1000).strftime("%Y-%m-%d %H:%M")
            r.add("INFO", "最后修改：%s（本机时间）" % when, "Last modified: %s (local time)" % when)
    if hashlib.sha256(src.encode("utf-8")).hexdigest() == AUDITED_FILE_SHA256:
        r.add("INFO", "整个文件与发布文件完全相同，说明文件头还没改过（③A、④ 未做）",
              "The whole file equals the released file, i.e. the header has not been edited yet (③A, ④ not done)")
    return r, (values("name") or ["?"])[0]


# --------------------------------------------------------------------------------------
# Locating storage folders
# --------------------------------------------------------------------------------------
def browser_roots():
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        roaming = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return [("chrome", "Chrome", os.path.join(local, "Google", "Chrome", "User Data")),
                ("edge", "Edge", os.path.join(local, "Microsoft", "Edge", "User Data")),
                ("brave", "Brave", os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")),
                ("chromium", "Chromium", os.path.join(local, "Chromium", "User Data")),
                ("opera", "Opera", os.path.join(roaming, "Opera Software", "Opera Stable"))]
    if sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
        return [("chrome", "Chrome", os.path.join(base, "Google", "Chrome")),
                ("edge", "Edge", os.path.join(base, "Microsoft Edge")),
                ("brave", "Brave", os.path.join(base, "BraveSoftware", "Brave-Browser")),
                ("chromium", "Chromium", os.path.join(base, "Chromium")),
                ("opera", "Opera", os.path.join(base, "com.operasoftware.Opera"))]
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return [("chrome", "Chrome", os.path.join(base, "google-chrome")),
            ("edge", "Edge", os.path.join(base, "microsoft-edge")),
            ("brave", "Brave", os.path.join(base, "BraveSoftware", "Brave-Browser")),
            ("chromium", "Chromium", os.path.join(base, "chromium")),
            ("opera", "Opera", os.path.join(base, "opera"))]


def profiles_in(root):
    """(profile folder name, path) for a browser user-data folder, or the folder itself
    when it already is a profile."""
    found = []
    if os.path.isdir(os.path.join(root, "Local Extension Settings")):
        found.append((os.path.basename(os.path.normpath(root)), root))
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(root, name)
        if os.path.isdir(os.path.join(path, "Local Extension Settings")):
            found.append((name, path))
    return found


def ext_label(ext_id):
    name, store, _ = KNOWN_EXTENSIONS.get(ext_id, ("extension " + ext_id, "--ext-id", False))
    return "%s (%s)" % (name, store)


def find_storages(args):
    ids = list(KNOWN_EXTENSIONS) + [i for i in (args.ext_id or []) if i not in KNOWN_EXTENSIONS]
    if args.storage_dir:
        return [("--storage-dir", args.ext_id[0] if args.ext_id else None, args.storage_dir)]
    if args.profile_dir:
        profiles = [("--profile-dir · " + name, path) for name, path in profiles_in(args.profile_dir)]
    else:
        profiles = []
        for key, label, root in browser_roots():
            if args.browser not in ("all", key):
                continue
            for name, path in profiles_in(root):
                if args.profile and name != args.profile:
                    continue
                profiles.append((label + " · " + name, path))
    storages = []
    for label, path in profiles:
        for ext_id in ids:
            d = os.path.join(path, "Local Extension Settings", ext_id)
            if os.path.isdir(d):
                storages.append((label, ext_id, d))
    return storages


# --------------------------------------------------------------------------------------
# Self-test of the readers (no browser data involved)
# --------------------------------------------------------------------------------------
def _put_varint(n):
    out_b = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out_b.append(b | 0x80)
        else:
            out_b.append(b)
            return bytes(out_b)


def _write_log(records):
    """Minimal LevelDB log writer, used only by --self-test."""
    buf = bytearray()
    for rec in records:
        left_data, first = rec, True
        while True:
            left = LOG_BLOCK - len(buf) % LOG_BLOCK
            if left < LOG_HEADER:
                buf += b"\0" * left
                left = LOG_BLOCK
            avail = left - LOG_HEADER
            frag, left_data = left_data[:avail], left_data[avail:]
            last = not left_data
            rtype = FULL if first and last else FIRST if first else LAST if last else MIDDLE
            crc = crc32c(frag, crc32c(bytes([rtype])))
            masked = ((((crc >> 15) | (crc << 17)) & 0xFFFFFFFF) + 0xA282EAD8) & 0xFFFFFFFF
            buf += struct.pack("<IHB", masked, len(frag), rtype) + frag
            first = False
            if last:
                break
    return bytes(buf)


def self_test():
    assert crc32c(b"123456789") == 0xE3069283
    assert snappy_decompress(bytes([12, 0x08]) + b"abc" + bytes([0x15, 0x03])) == b"abc" * 4
    assert snappy_decompress(bytes([5, 0x10]) + b"hello") == b"hello"
    for broken in (bytes([12, 0x08]) + b"abc" + bytes([0x15, 0x09]), bytes([9, 0x10]) + b"hello"):
        try:
            snappy_decompress(broken)
            raise AssertionError("corrupt snappy accepted")
        except CorruptError:
            pass
    big = json.dumps({"origin": "normal", "value": "x" * 100000}).encode()
    batch1 = struct.pack("<QI", 10, 2) + b"\x01" + _put_varint(9) + b"k@meta#u1" + _put_varint(2) + b"{}" \
        + b"\x01" + _put_varint(11) + b"k@source#u1" + _put_varint(len(big)) + big
    batch2 = struct.pack("<QI", 12, 1) + b"\x00" + _put_varint(9) + b"k@meta#u1"
    log = _write_log([batch1, batch2])
    stats = {"records": 0, "bad": 0, "torn": 0}
    entries = [e for rec in iter_log_records(log, stats) for e in iter_write_batch(rec)]
    assert stats == {"records": 2, "bad": 0, "torn": 0}, stats
    assert [(s, k) for s, k, _ in entries] == [(10, b"k@meta#u1"), (11, b"k@source#u1"), (12, b"k@meta#u1")]
    assert entries[1][2] == big and entries[2][2] is None
    damaged = bytearray(log)
    damaged[LOG_BLOCK + 100] ^= 0xFF                      # corrupt a MIDDLE fragment
    stats = {"records": 0, "bad": 0, "torn": 0}
    assert [len(r) for r in iter_log_records(bytes(damaged), stats)] == [len(batch2)] and stats["bad"] >= 1
    print("self-test OK: crc32c, snappy, log fragments (FULL/FIRST/MIDDLE/LAST), write batches, corruption handling")


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def load_audited_file(path):
    with open(path, "rb") as f:
        data = f.read()
    if hashlib.sha256(data).hexdigest() != AUDITED_FILE_SHA256:
        out("错误：--audited-file 不是审计过的文件（SHA-256 不符）。",
            "Error: --audited-file is not the audited file (SHA-256 mismatch).")
        sys.exit(2)
    text = data.decode("utf-8")
    body = text[text.index(END_MARK) + len(END_MARK):]
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == AUDITED_BODY_SHA256
    return body


def main():
    global LANG
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Read-only check of the BTR userscript installed in Tampermonkey "
                                             "(audited commit 0302b34, updates off). See tools/README.en.md.")
    ap.add_argument("--browser", default="all", choices=["all", "chrome", "edge", "brave", "chromium", "opera"])
    ap.add_argument("--profile", help='profile folder name, e.g. "Default" or "Profile N" (default: all)')
    ap.add_argument("--profile-dir", help="path to a browser profile folder (or a user-data folder)")
    ap.add_argument("--storage-dir", help="path to the extension's LevelDB folder itself (e.g. an offline copy)")
    ap.add_argument("--ext-id", action="append", help="extra extension ID to look for (repeatable)")
    ap.add_argument("--name", help='match scripts whose @name contains this text (default: "%s" or the BTR '
                                   '@namespace)' % DEFAULT_NAME)
    ap.add_argument("--audited-file", help="a saved copy of the pinned file; used to locate the first difference")
    ap.add_argument("--lang", default="both", choices=["both", "zh", "en"])
    ap.add_argument("--self-test", action="store_true", help="test the built-in readers and exit")
    args = ap.parse_args()
    LANG = args.lang

    if args.self_test:
        self_test()
        return 0

    audited_body = load_audited_file(args.audited_file) if args.audited_file else None

    out("verify-tm-install %s · 只读校验 BTR 安装（审计提交 0302b34 · v%s）" % (TOOL_VERSION, AUDITED_VERSION),
        "verify-tm-install %s · read-only check of the BTR install (audited commit 0302b34 · v%s)"
        % (TOOL_VERSION, AUDITED_VERSION))
    storages = find_storages(args)
    if not storages:
        out("没找到 Tampermonkey 的存储目录。用 --profile-dir 指定浏览器个人资料目录，或用 --ext-id 指定扩展 ID。",
            "No Tampermonkey storage folder found. Point --profile-dir at a browser profile, or pass --ext-id.")
        return 2

    any_found, any_fail = False, False
    for label, ext_id, folder in storages:
        print()
        out("== %s · %s ==" % (label, ext_label(ext_id) if ext_id else "LevelDB"),
            "== %s · %s ==" % (label, ext_label(ext_id) if ext_id else "LevelDB"))
        warnings, info = [], {}
        latest = load_latest(folder, warnings, info)
        out("  读取：%d 个 .log、%d 个 .ldb（MANIFEST %s），%d 条日志记录、%d 个表数据块"
            % (info["logs"], info["tables"], "已解析" if info["manifest"] else "未用", info["log_records"],
               info["blocks"]),
            "  Read: %d .log + %d .ldb file(s) (MANIFEST %s), %d log records, %d table blocks"
            % (info["logs"], info["tables"], "parsed" if info["manifest"] else "not used", info["log_records"],
               info["blocks"]))
        for zh, en in warnings:
            out("  [WARN] " + zh, "  [WARN] " + en)
        if ext_id and KNOWN_EXTENSIONS.get(ext_id, (None, None, False))[2]:
            out("  [WARN] 这是 Tampermonkey BETA；05 §1 建议使用正式版。",
                "  [WARN] This is Tampermonkey BETA; 05 §1 recommends the stable version.")

        scripts = []
        n_scripts = 0
        for key, (seq, raw) in latest.items():
            if b"@source#" not in key or raw is None:
                continue
            try:
                src = json_value(raw)
            except Exception:                              # not JSON text: not a script record
                continue
            if not isinstance(src, str):
                continue
            n_scripts += 1
            parts = split_source(src)
            hdr = parse_header(header_lines(parts[1])) if parts else []
            names = [v for k, v, _ in hdr if k == "name" or k.startswith("name:")]
            namespace = [v for k, v, _ in hdr if k == "namespace"]
            if args.name:
                hit = any(args.name in n for n in names)
            else:
                hit = any(DEFAULT_NAME in n for n in names) or BTR_NAMESPACE in namespace
            if not hit:
                continue
            meta = None
            meta_raw = latest.get(key.replace(b"@source#", b"@meta#", 1))
            if meta_raw and meta_raw[1] is not None:
                try:
                    meta = json_value(meta_raw[1])
                    meta = meta if isinstance(meta, dict) else None
                except Exception:
                    meta = None
            scripts.append((src, meta))
        out("  共 %d 个已安装脚本，匹配到 %d 个" % (n_scripts, len(scripts)),
            "  %d installed script(s), %d matched" % (n_scripts, len(scripts)))
        if not scripts:
            continue
        any_found = True
        if len(scripts) > 1:
            out("  [WARN] 同一个脚本装了 %d 份：会被注入多次，只保留一份。" % len(scripts),
                "  [WARN] %d copies installed: it will be injected more than once; keep only one." % len(scripts))
        for idx, (src, meta) in enumerate(scripts, 1):
            res, name = check_script(src, meta, audited_body)
            print()
            out("  脚本 %d/%d：%s" % (idx, len(scripts), name), "  Script %d/%d: %s" % (idx, len(scripts), name))
            res.show()
            failed = res.failed
            print()
            if failed:
                any_fail = True
                out("  结论：FAIL，%d 项未通过（见上方 → 修复）。" % len(failed),
                    "  Verdict: FAIL, %d check(s) failed (see the → Fix lines above)." % len(failed))
            else:
                out("  结论：PASS，已安装的 BTR 与审计提交 0302b34 一致，文件头按指南改好，自动更新已关闭。",
                    "  Verdict: PASS. The installed BTR matches audited commit 0302b34, the header is edited "
                    "as in the guide, and updates are off.")

    print()
    if not any_found:
        out("没有找到 BTR。若刚改过设置，请在 Tampermonkey 里对脚本做一次改动后重跑；也可以用 --name 指定名称。",
            "BTR was not found. If you just changed something, make a change on the script in Tampermonkey and "
            "re-run, or use --name.")
        return 2
    out("提示：本工具只核对存储里的记录；页面上是否真的生效，仍按 05 §2 ⑤ 在浏览器里看一遍（悬浮球、passport 页面）。",
        "Note: this checks the stored record only; still confirm in the browser per 05 §2 ⑤ "
        "(the floating button, the passport page).")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
