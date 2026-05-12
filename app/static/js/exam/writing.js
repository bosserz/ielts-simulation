/**
 * Writing module: word count + autosave.
 *
 * Word count:
 *   Uses an uncontrolled textarea and a native `input` event listener that
 *   updates a DOM element directly — no framework re-renders, stays at 60fps
 *   even for long essays.
 *
 * Autosave:
 *   Debounced: fires 10 seconds after the last keystroke.
 *   POSTs to /api/writing/<sessionId>/autosave.
 *   Failure is silenced; the draft is preserved in the textarea until next save.
 */

const sessionId = window.EXAM_SESSION_ID;
const editor = document.getElementById("writing-editor");
const wordCountEl = document.getElementById("word-count");
const autosaveStatusEl = document.getElementById("autosave-status");
const taskIndicator = document.getElementById("task-indicator");

let _currentTask = 1;
let _autosaveTimer = null;

// Restore previous draft
if (editor) {
  editor.value = _currentTask === 1
    ? (window.TASK1_DRAFT || "")
    : (window.TASK2_DRAFT || "");
  _updateWordCount();
}

// Live word count — updates DOM directly, bypasses any reactivity overhead
editor?.addEventListener("input", () => {
  _updateWordCount();
  _scheduleAutosave();
});

function _updateWordCount() {
  const text = editor?.value?.trim() ?? "";
  const count = text ? text.split(/\s+/).length : 0;
  if (wordCountEl) wordCountEl.textContent = count;
}

function _scheduleAutosave() {
  clearTimeout(_autosaveTimer);
  _autosaveTimer = setTimeout(_doAutosave, 10_000);
}

async function _doAutosave() {
  const text = editor?.value ?? "";
  if (autosaveStatusEl) autosaveStatusEl.textContent = "Saving…";
  try {
    const res = await fetch(`/api/writing/${sessionId}/autosave`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: _currentTask, text }),
    });
    if (res.ok) {
      if (autosaveStatusEl) autosaveStatusEl.textContent = `Draft saved at ${_timeNow()}`;
    } else {
      if (autosaveStatusEl) autosaveStatusEl.textContent = "Save failed — retrying…";
      _autosaveTimer = setTimeout(_doAutosave, 30_000);
    }
  } catch {
    if (autosaveStatusEl) autosaveStatusEl.textContent = "Offline — draft held locally";
    _autosaveTimer = setTimeout(_doAutosave, 30_000);
  }
}

// ---------------------------------------------------------------------------
// Task tab switching (Task 1 / Task 2)
// ---------------------------------------------------------------------------

const _drafts = { 1: window.TASK1_DRAFT || "", 2: window.TASK2_DRAFT || "" };

document.querySelectorAll(".task-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const task = parseInt(btn.dataset.task, 10);
    if (task === _currentTask) return;

    // Save current draft in memory
    _drafts[_currentTask] = editor?.value ?? "";

    _currentTask = task;
    if (editor) editor.value = _drafts[_currentTask];
    _updateWordCount();

    // Update prompt visibility
    document.getElementById("task1-prompt")?.classList.toggle("hidden", task !== 1);
    document.getElementById("task2-prompt")?.classList.toggle("hidden", task !== 2);

    // Update tab button styles
    document.querySelectorAll(".task-tab-btn").forEach((b) => {
      const isActive = parseInt(b.dataset.task, 10) === task;
      b.classList.toggle("bg-ielts-blue", isActive);
      b.classList.toggle("text-white", isActive);
      b.classList.toggle("border-gray-300", !isActive);
      b.classList.toggle("text-gray-700", !isActive);
    });

    if (taskIndicator) taskIndicator.textContent = `Task ${task}`;
    editor?.focus();
  });
});

// Autosave on page unload (best effort)
window.addEventListener("beforeunload", () => {
  const text = editor?.value ?? "";
  if (!text) return;
  navigator.sendBeacon(
    `/api/writing/${sessionId}/autosave`,
    new Blob([JSON.stringify({ task: _currentTask, text })], { type: "application/json" }),
  );
});

function _timeNow() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
