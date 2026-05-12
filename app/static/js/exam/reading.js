/**
 * Reading module: text highlight and annotation system.
 *
 * Features:
 *   - mouseup on passage pane → detect text selection → show context menu
 *   - Context menu options: Highlight (yellow/pink/blue), Add Note
 *   - Highlights stored in the DOM via <mark> elements and persisted to the server
 *   - Existing annotations loaded from window.EXISTING_ANNOTATIONS on init
 *
 * Right-click is blocked globally within the exam shell (shell.html).
 * The context menu appears on mouseup with a non-empty selection instead.
 */

import { writeAnswer, readAllAnswers } from "./indexeddb.js";
import { markAnswered } from "./navigation.js";

const sessionId = window.EXAM_SESSION_ID;
const passageGroupId = window.PASSAGE_GROUP_ID;

const passagePane = document.getElementById("passage-pane");
const highlightMenu = document.getElementById("highlight-menu");
const notePopover = document.getElementById("note-popover");
const noteTextarea = document.getElementById("note-text");

let _selection = null;
let _selectionRange = null;
let _pendingColor = null;

// ---------------------------------------------------------------------------
// Selection detection
// ---------------------------------------------------------------------------

// Block the browser native context menu on the passage pane so the custom
// annotation menu is the only option. The custom menu fires on mouseup instead.
passagePane?.addEventListener("contextmenu", (e) => e.preventDefault());

passagePane?.addEventListener("mouseup", (e) => {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.toString().trim()) {
    _hideMenu();
    return;
  }

  _selection = sel.toString().trim();
  _selectionRange = sel.getRangeAt(0).cloneRange();

  const rect = sel.getRangeAt(0).getBoundingClientRect();
  _showMenuAt(rect.left + window.scrollX, rect.bottom + window.scrollY + 4);
});

document.addEventListener("mousedown", (e) => {
  if (!highlightMenu?.contains(e.target) && !notePopover?.contains(e.target)) {
    _hideMenu();
    _hideNotePopover();
  }
});

// ---------------------------------------------------------------------------
// Highlight actions
// ---------------------------------------------------------------------------

document.getElementById("btn-highlight-yellow")?.addEventListener("click", () => _applyHighlight("yellow"));
document.getElementById("btn-highlight-pink")?.addEventListener("click", () => _applyHighlight("pink"));
document.getElementById("btn-highlight-blue")?.addEventListener("click", () => _applyHighlight("blue"));

document.getElementById("btn-add-note")?.addEventListener("click", () => {
  _pendingColor = "yellow";
  _hideMenu();
  const rect = _selectionRange?.getBoundingClientRect();
  if (rect) _showNotePopoverAt(rect.right + window.scrollX + 8, rect.top + window.scrollY);
});

document.getElementById("btn-note-cancel")?.addEventListener("click", _hideNotePopover);

document.getElementById("btn-note-save")?.addEventListener("click", () => {
  const note = noteTextarea.value.trim();
  if (_selectionRange) {
    _applyHighlight(_pendingColor || "yellow", note);
  }
  _hideNotePopover();
  noteTextarea.value = "";
});

// ---------------------------------------------------------------------------
// Apply highlight to DOM + save to server
// ---------------------------------------------------------------------------

async function _applyHighlight(color, note = null) {
  if (!_selectionRange || !_selection) return;
  _hideMenu();

  // Calculate character offsets within the passage text
  const passageText = document.getElementById("passage-text");
  const { startOffset, endOffset } = _computeOffsets(_selectionRange, passageText);

  // Wrap selection in <mark>
  const mark = document.createElement("mark");
  mark.dataset.color = color;
  mark.dataset.note = note || "";
  mark.className = `highlight-${color}`;
  if (note) mark.title = note;

  try {
    _selectionRange.surroundContents(mark);
  } catch {
    // Complex range (crosses element boundaries): use extractContents
    const fragment = _selectionRange.extractContents();
    mark.appendChild(fragment);
    _selectionRange.insertNode(mark);
  }

  window.getSelection()?.removeAllRanges();

  // Persist to server
  try {
    await fetch("/api/annotations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        passage_group_id: passageGroupId,
        start_offset: startOffset,
        end_offset: endOffset,
        selected_text: _selection,
        note,
        color,
      }),
    });
  } catch {
    // Offline: annotation is in DOM; will be lost on reload if not synced.
    // Full IDB-backed annotation persistence is a Phase 2 enhancement.
  }

  _selection = null;
  _selectionRange = null;
}

// ---------------------------------------------------------------------------
// Restore existing annotations on page load
// ---------------------------------------------------------------------------

function _restoreAnnotations() {
  const existing = window.EXISTING_ANNOTATIONS || [];
  // For now, annotations are re-applied by the server rendering passage HTML
  // with stored offsets. Full client-side restoration is a Phase 2 enhancement.
  // This stub is kept for future implementation.
}

// ---------------------------------------------------------------------------
// Answer input → IndexedDB
// ---------------------------------------------------------------------------

document.querySelectorAll(".answer-input").forEach((input) => {
  input.addEventListener("change", (e) => {
    const questionId = e.target.dataset.questionId;
    const value = e.target.type === "radio"
      ? (e.target.checked ? e.target.value : null)
      : e.target.value;
    if (questionId && value !== null) {
      writeAnswer(sessionId, questionId, value);
      markAnswered(questionId);
    }
  });
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function _computeOffsets(range, container) {
  const preRange = document.createRange();
  preRange.selectNodeContents(container);
  preRange.setEnd(range.startContainer, range.startOffset);
  const startOffset = preRange.toString().length;
  return {
    startOffset,
    endOffset: startOffset + range.toString().length,
  };
}

function _showMenuAt(x, y) {
  if (!highlightMenu) return;
  highlightMenu.style.left = `${x}px`;
  highlightMenu.style.top = `${y}px`;
  highlightMenu.classList.remove("hidden");
}

function _hideMenu() {
  highlightMenu?.classList.add("hidden");
}

function _showNotePopoverAt(x, y) {
  if (!notePopover) return;
  notePopover.style.left = `${x}px`;
  notePopover.style.top = `${y}px`;
  notePopover.classList.remove("hidden");
  noteTextarea.focus();
}

function _hideNotePopover() {
  notePopover?.classList.add("hidden");
}

_restoreAnnotations();

// Restore saved answers from IDB on page load
(async () => {
  const saved = await readAllAnswers(sessionId);
  for (const { questionId, value } of saved) {
    // Radio (MCQ, TFNG, YNGNG)
    const radio = document.querySelector(`.answer-input[data-question-id="${questionId}"][value="${value}"]`);
    if (radio) { radio.checked = true; markAnswered(questionId); continue; }
    // Select (MATCHING_HEADINGS)
    const sel = document.querySelector(`select.answer-input[data-question-id="${questionId}"]`);
    if (sel) { sel.value = value; if (value) markAnswered(questionId); continue; }
    // Text input
    const text = document.querySelector(`input.answer-input[data-question-id="${questionId}"]`);
    if (text) { text.value = value; if (value) markAnswered(questionId); }
  }
})();
