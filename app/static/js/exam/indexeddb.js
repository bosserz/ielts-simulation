/**
 * IndexedDB persistence layer for the exam session.
 *
 * Uses a write-ahead log (WAL) pattern:
 *   1. Every answer mutation is appended as an event to the `events` store.
 *   2. A background worker flushes unsynced events to the server in batches.
 *   3. On page reload, usynced events are replayed on top of the server state.
 *
 * Object stores:
 *   events       — append-only write-ahead log
 *   answers      — materialized current answer state
 *   audio_cache  — pre-loaded AudioBuffer binary for Listening
 *   timer_state  — { timeRemainingS, lastUpdated }
 */

const DB_VERSION = 1;

let _db = null;
let _syncTimer = null;

export async function openDB(sessionId) {
  if (_db) return _db;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(`ielts_session_${sessionId}`, DB_VERSION);

    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains("events")) {
        const store = db.createObjectStore("events", { keyPath: "eventId", autoIncrement: true });
        store.createIndex("by_synced", "synced", { unique: false });
      }
      if (!db.objectStoreNames.contains("answers")) {
        db.createObjectStore("answers", { keyPath: "questionId" });
      }
      if (!db.objectStoreNames.contains("audio_cache")) {
        db.createObjectStore("audio_cache", { keyPath: "sectionId" });
      }
      if (!db.objectStoreNames.contains("timer_state")) {
        db.createObjectStore("timer_state", { keyPath: "id" });
      }
    };

    request.onsuccess = (e) => {
      _db = e.target.result;
      resolve(_db);
    };
    request.onerror = (e) => reject(e.target.error);
  });
}

function tx(storeName, mode = "readonly") {
  return _db.transaction(storeName, mode).objectStore(storeName);
}

/** Append an event and update the materialized answers store. */
export async function writeAnswer(sessionId, questionId, newValue) {
  const db = await openDB(sessionId);

  await new Promise((resolve, reject) => {
    const t = db.transaction(["events", "answers"], "readwrite");
    t.objectStore("events").add({
      timestamp: Date.now(),
      questionId,
      newValue,
      synced: false,
    });
    t.objectStore("answers").put({ questionId, value: newValue, updatedAt: Date.now() });
    t.oncomplete = resolve;
    t.onerror = (e) => reject(e.target.error);
  });

  // Save directly to the server immediately (belt-and-suspenders on top of the
  // 3-second background flush, so a fast-clicking student doesn't lose answers).
  _saveDirectly(sessionId, questionId, newValue);

  _scheduleSyncFlush(sessionId);
}

const _directSaveTimers = {};

function _saveDirectly(sessionId, questionId, newValue) {
  // Debounce per question — 800 ms so rapid typing doesn't spam the server.
  clearTimeout(_directSaveTimers[questionId]);
  _directSaveTimers[questionId] = setTimeout(async () => {
    if (!navigator.onLine) return;
    try {
      await fetch(`/api/sessions/${sessionId}/answers/batch`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: [{ questionId, newValue }] }),
      });
    } catch { /* offline — IDB flush on submit will catch it */ }
  }, 800);
}

export async function readAnswer(sessionId, questionId) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const req = tx("answers").get(questionId);
    req.onsuccess = () => resolve(req.result?.value ?? null);
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function readAllAnswers(sessionId) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const results = [];
    const req = tx("answers").openCursor();
    req.onsuccess = (e) => {
      const cursor = e.target.result;
      if (cursor) { results.push(cursor.value); cursor.continue(); }
      else resolve(results);
    };
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function storeAudioBuffer(sessionId, sectionId, arrayBuffer) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const req = tx("audio_cache", "readwrite").put({ sectionId, data: arrayBuffer, cachedAt: Date.now() });
    req.onsuccess = resolve;
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function getAudioBuffer(sessionId, sectionId) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const req = tx("audio_cache").get(sectionId);
    req.onsuccess = () => resolve(req.result?.data ?? null);
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function saveTimerState(sessionId, timeRemainingS) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const req = tx("timer_state", "readwrite").put({ id: "current", timeRemainingS, savedAt: Date.now() });
    req.onsuccess = resolve;
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function readTimerState(sessionId) {
  const db = await openDB(sessionId);
  return new Promise((resolve, reject) => {
    const req = tx("timer_state").get("current");
    req.onsuccess = () => resolve(req.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

// ---------------------------------------------------------------------------
// Sync flush: batch-POST unsynced events to the server
// ---------------------------------------------------------------------------

function _scheduleSyncFlush(sessionId) {
  clearTimeout(_syncTimer);
  _syncTimer = setTimeout(() => _flushToServer(sessionId), 3000);
}

async function _flushToServer(sessionId) {
  if (!navigator.onLine) return;

  const db = await openDB(sessionId);
  const unsyncedEvents = await new Promise((resolve, reject) => {
    const results = [];
    const index = db.transaction("events", "readonly")
      .objectStore("events")
      .index("by_synced")
      .openCursor(IDBKeyRange.only(false));
    index.onsuccess = (e) => {
      const cursor = e.target.result;
      if (cursor) { results.push(cursor.value); cursor.continue(); }
      else resolve(results);
    };
    index.onerror = (e) => reject(e.target.error);
  });

  if (!unsyncedEvents.length) return;

  try {
    const res = await fetch(`/api/sessions/${sessionId}/answers/batch`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: unsyncedEvents }),
    });
    if (!res.ok) return;

    // Mark events as synced
    const t = db.transaction("events", "readwrite");
    const store = t.objectStore("events");
    for (const evt of unsyncedEvents) {
      const req = store.get(evt.eventId);
      req.onsuccess = () => {
        const record = req.result;
        if (record) { record.synced = true; store.put(record); }
      };
    }
  } catch {
    // Network error: will retry on next write
  }
}

// Flush on reconnect
window.addEventListener("online", () => {
  const sessionId = window.EXAM_SESSION_ID;
  if (sessionId) _flushToServer(sessionId);
});

/** Force an immediate server sync. Called before page navigation. */
export async function flushToServer(sessionId) {
  return _flushToServer(sessionId);
}
