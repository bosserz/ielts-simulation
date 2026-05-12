/**
 * AudioPlayer — one-time playback enforcer for the Listening section.
 *
 * Supports both single-audio and multi-part (Part 1–4) configurations.
 *
 * Single-part flow:
 *   1. Fetch signed URL → download → cache in IndexedDB.
 *   2. play() fires once; server records audio_played_at.
 *   3. After audio ends, 2-minute checking timer starts.
 *
 * Multi-part flow:
 *   1. Pre-load all N part audio files (sequential; IDB-cached per part).
 *   2. play() starts Part 1; parts advance automatically with a 2 s gap.
 *   3. Server is notified once (when Part 1 starts).
 *   4. Checking timer starts after the final part ends.
 */

import { storeAudioBuffer, getAudioBuffer } from "./indexeddb.js";

export class AudioPlayer {
  /**
   * @param {{
   *   sessionId: string,
   *   audioUrlBase: string,   // e.g. /api/sessions/<id>/audio-url
   *   alreadyPlayed: boolean,
   *   audioPlayedUrl: string,
   * }} opts
   */
  constructor({ sessionId, audioUrlBase, alreadyPlayed, audioPlayedUrl }) {
    this._sessionId     = sessionId;
    this._audioUrlBase  = audioUrlBase;
    this._alreadyPlayed = alreadyPlayed;
    this._audioPlayedUrl = audioPlayedUrl;

    this._context      = null;
    this._hasPlayed    = alreadyPlayed;
    this._isReady      = false;
    this._parts        = [];      // metadata from API: [{label, groupId, …}]
    this._partBuffers  = [];      // decoded AudioBuffer per part
    this._isMultiPart  = false;

    this._statusEl        = document.getElementById("audio-status");
    this._playBtn         = document.getElementById("btn-play-audio");
    this._partIndicatorEl = document.getElementById("audio-part-indicator");

    if (alreadyPlayed) {
      this._lockControls("Recording already played.");
    } else {
      this._init();
    }
  }

  // ---------------------------------------------------------------------------
  // Initialisation
  // ---------------------------------------------------------------------------

  async _init() {
    this._setStatus("Loading audio…");
    try {
      this._context = new AudioContext();

      // Discover parts from API
      const { url, parts } = await this._fetchMeta();
      this._parts = parts || [];
      this._isMultiPart = this._parts.length > 1;

      if (this._isMultiPart) {
        await this._loadMultiPart();
      } else {
        await this._loadSinglePart(url);
      }

      this._isReady = true;
      this._setStatus("Audio ready. Click Play when you are ready to begin.");
      if (this._playBtn) this._playBtn.disabled = false;
    } catch (err) {
      this._setStatus("Audio load failed. Please contact your invigilator.");
      console.error("[AudioPlayer]", err);
    }
  }

  async _fetchMeta() {
    const res = await fetch(this._audioUrlBase);
    if (!res.ok) throw new Error("Failed to fetch audio metadata.");
    return res.json();
  }

  async _fetchPartUrl(partIndex) {
    const res = await fetch(`${this._audioUrlBase}?partIndex=${partIndex}`);
    if (!res.ok) throw new Error(`Failed to fetch URL for part ${partIndex}.`);
    const data = await res.json();
    return data.url;
  }

  async _loadBuffer(url, cacheKey) {
    // IDB cache hit
    let raw = await getAudioBuffer(this._sessionId, cacheKey);
    if (!raw) {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status} fetching audio.`);
      raw = await res.arrayBuffer();
      await storeAudioBuffer(this._sessionId, cacheKey, raw);
    }
    return raw;
  }

  async _loadSinglePart(url) {
    if (!url) throw new Error("No audio URL returned from server.");
    const raw = await this._loadBuffer(url, "part_0");
    this._partBuffers[0] = await this._context.decodeAudioData(raw.slice(0));
  }

  async _loadMultiPart() {
    // Fetch all signed URLs in parallel, then download sequentially (IDB safety)
    const urls = await Promise.all(
      this._parts.map((_, i) => this._fetchPartUrl(i).catch(() => null))
    );

    for (let i = 0; i < this._parts.length; i++) {
      this._setStatus(`Loading audio… (${i + 1}/${this._parts.length})`);
      if (!urls[i]) { this._partBuffers.push(null); continue; }
      const raw = await this._loadBuffer(urls[i], `part_${i}`);
      this._partBuffers.push(await this._context.decodeAudioData(raw.slice(0)));
    }

    this._updatePartPills(-1); // show all parts, none active yet
  }

  // ---------------------------------------------------------------------------
  // Playback
  // ---------------------------------------------------------------------------

  /** Plays the audio exactly once. Subsequent calls are no-ops. */
  async play() {
    if (this._hasPlayed || !this._isReady) return;
    this._hasPlayed = true;

    // Notify server before playback — guards against browser crash
    try { await fetch(this._audioPlayedUrl, { method: "POST" }); } catch { /* ok */ }

    await this._context.resume();
    this._playPart(0);
  }

  _playPart(idx) {
    const buf = this._partBuffers[idx];
    if (!buf) {
      // Part has no audio — skip to next
      const next = idx + 1;
      if (next < this._parts.length) {
        this._playPart(next);
      } else {
        this._onAllPartsFinished();
      }
      return;
    }

    const label = this._parts[idx]?.label || `Part ${idx + 1}`;
    this._lockControls(`Playing ${label}…`);
    this._updatePartPills(idx);

    const source = this._context.createBufferSource();
    source.buffer = buf;
    source.connect(this._context.destination);
    source.start(0);

    source.onended = () => {
      const next = idx + 1;
      if (next < this._parts.length) {
        const nextLabel = this._parts[next]?.label || `Part ${next + 1}`;
        this._setStatus(`${label} finished. ${nextLabel} starting in 2 s…`);
        setTimeout(() => this._playPart(next), 2000);
      } else {
        this._onAllPartsFinished();
      }
    };
  }

  _onAllPartsFinished() {
    this._lockControls("Recording finished. Checking time: 2 minutes.");
    this._updatePartPills(this._parts.length); // mark all as done
    this._startCheckingTimer(120);
  }

  // ---------------------------------------------------------------------------
  // UI helpers
  // ---------------------------------------------------------------------------

  /**
   * Update the part pill indicators (only shown for multi-part).
   * activeIdx === -1 → all pending; activeIdx >= parts.length → all done.
   */
  _updatePartPills(activeIdx) {
    if (!this._isMultiPart || !this._partIndicatorEl) return;

    // Build or refresh pill elements
    if (!this._partIndicatorEl.children.length) {
      this._parts.forEach((p, i) => {
        const pill = document.createElement("span");
        pill.id = `audio-part-pill-${i}`;
        pill.className = "audio-part-pill inline-block px-3 py-1 rounded-full text-xs font-medium mr-1 bg-gray-100 text-gray-500";
        pill.textContent = p.label || `Part ${i + 1}`;
        this._partIndicatorEl.appendChild(pill);
      });
    }

    this._parts.forEach((_, i) => {
      const pill = document.getElementById(`audio-part-pill-${i}`);
      if (!pill) return;
      if (i < activeIdx) {
        pill.className = "audio-part-pill inline-block px-3 py-1 rounded-full text-xs font-medium mr-1 bg-gray-200 text-gray-400 line-through";
      } else if (i === activeIdx) {
        pill.className = "audio-part-pill inline-block px-3 py-1 rounded-full text-xs font-medium mr-1 bg-ielts-blue text-white";
      } else {
        pill.className = "audio-part-pill inline-block px-3 py-1 rounded-full text-xs font-medium mr-1 bg-gray-100 text-gray-500";
      }
    });
  }

  _lockControls(message) {
    if (this._playBtn) {
      this._playBtn.disabled = true;
      this._playBtn.textContent = "⏹ Played";
      this._playBtn.classList.add("opacity-50", "cursor-not-allowed");
    }
    this._setStatus(message);
  }

  _setStatus(msg) {
    if (this._statusEl) this._statusEl.textContent = msg;
  }

  _startCheckingTimer(seconds) {
    let remaining = seconds;
    const timerEl = document.getElementById("timer-display");
    const interval = setInterval(() => {
      remaining -= 1;
      const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
      const secs = String(remaining % 60).padStart(2, "0");
      if (timerEl) timerEl.textContent = `${mins}:${secs}`;
      this._setStatus(`Checking time: ${mins}:${secs}`);
      if (remaining <= 0) {
        clearInterval(interval);
        document.getElementById("btn-submit")?.click();
      }
    }, 1000);
  }
}
