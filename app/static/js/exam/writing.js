/**
 * Writing module: word count + keep hidden form inputs in sync.
 *
 * The student's essays for Task 1 and Task 2 are written to hidden inputs
 * inside the submit form so they're included automatically in the POST body
 * when the form submits — no fetch, no async hooks, no timing issues.
 */

const editor = document.getElementById("writing-editor");
const wordCountEl = document.getElementById("word-count");
const taskIndicator = document.getElementById("task-indicator");
const task1Hidden = document.getElementById("task1-hidden");
const task2Hidden = document.getElementById("task2-hidden");

let _currentTask = 1;
const _drafts = { 1: window.TASK1_DRAFT || "", 2: window.TASK2_DRAFT || "" };

// Initialize editor + hidden inputs
if (editor) {
  editor.value = _drafts[_currentTask];
  _updateWordCount();
}
if (task1Hidden) task1Hidden.value = _drafts[1];
if (task2Hidden) task2Hidden.value = _drafts[2];

// Live word count + sync current task to hidden input
editor?.addEventListener("input", () => {
  _updateWordCount();
  _drafts[_currentTask] = editor.value;
  _syncHidden(_currentTask);
});

function _updateWordCount() {
  const text = editor?.value?.trim() ?? "";
  const count = text ? text.split(/\s+/).length : 0;
  if (wordCountEl) wordCountEl.textContent = count;
}

function _syncHidden(task) {
  const el = task === 1 ? task1Hidden : task2Hidden;
  if (el) el.value = _drafts[task];
}

// ---------------------------------------------------------------------------
// Task tab switching
// ---------------------------------------------------------------------------

document.querySelectorAll(".task-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const task = parseInt(btn.dataset.task, 10);
    if (task === _currentTask) return;

    _drafts[_currentTask] = editor?.value ?? "";
    _syncHidden(_currentTask);
    _currentTask = task;
    if (editor) editor.value = _drafts[_currentTask];
    _updateWordCount();

    document.getElementById("task1-prompt")?.classList.toggle("hidden", task !== 1);
    document.getElementById("task2-prompt")?.classList.toggle("hidden", task !== 2);

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
