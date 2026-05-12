/**
 * Exam countdown timer.
 *
 * States:
 *   normal  → white text on blue header
 *   warning → amber background (≤ 10 min)
 *   danger  → red background, pulsing (≤ 5 min)
 *
 * Sends a heartbeat POST every 60 seconds to keep the server's
 * time_remaining_s authoritative (prevents client-side manipulation).
 */

import { saveTimerState } from "./indexeddb.js";

let _intervalId = null;
let _seconds = 0;
let _sessionId = null;
let _heartbeatUrl = null;
let _lastHeartbeat = 0;
const HEARTBEAT_INTERVAL = 60_000; // ms

/**
 * @param {{ sessionId: string, initialSeconds: number, heartbeatUrl: string }} opts
 */
export function initTimer({ sessionId, initialSeconds, heartbeatUrl }) {
  _sessionId = sessionId;
  _heartbeatUrl = heartbeatUrl;
  _seconds = initialSeconds;

  _render();
  _intervalId = setInterval(_tick, 1000);
}

export function getSecondsRemaining() {
  return _seconds;
}

export function stopTimer() {
  clearInterval(_intervalId);
}

function _tick() {
  if (_seconds <= 0) {
    stopTimer();
    _onTimeUp();
    return;
  }

  _seconds -= 1;
  _render();

  // Persist to IDB every 5 seconds
  if (_seconds % 5 === 0) {
    saveTimerState(_sessionId, _seconds);
  }

  // Heartbeat every 60 seconds
  const now = Date.now();
  if (now - _lastHeartbeat >= HEARTBEAT_INTERVAL) {
    _lastHeartbeat = now;
    _sendHeartbeat();
  }
}

function _render() {
  const el = document.getElementById("timer-display");
  if (!el) return;

  const mins = Math.floor(_seconds / 60);
  const secs = _seconds % 60;
  el.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  el.classList.remove("timer--warning", "timer--danger");
  if (_seconds <= 300) {          // ≤ 5 minutes
    el.classList.add("timer--danger");
  } else if (_seconds <= 600) {  // ≤ 10 minutes
    el.classList.add("timer--warning");
  }
}

function _sendHeartbeat() {
  if (!navigator.onLine || !_heartbeatUrl) return;
  fetch(_heartbeatUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ time_remaining_s: _seconds }),
  }).catch(() => {});
}

function _onTimeUp() {
  const el = document.getElementById("timer-display");
  if (el) el.textContent = "00:00";
  // Auto-submit: trigger the submit button if it exists
  const submitBtn = document.getElementById("btn-submit");
  if (submitBtn) {
    submitBtn.click();
  }
}
