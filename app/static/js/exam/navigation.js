/**
 * Question navigation for exam sections.
 *
 * Manages:
 *   - Current question tracking
 *   - Previous / Next button logic
 *   - Navigation button visual states (answered / flagged)
 *   - Flag toggle with server sync
 *
 * Usage:
 *   import { initNavigation, markAnswered } from "./navigation.js";
 *   initNavigation({ sessionId: "abc123" });
 *
 *   // Call after writing an answer:
 *   markAnswered(questionId);
 */

let _questions = [];
let _currentIdx = 0;
let _sessionId = null;

/**
 * @param {{ sessionId: string, lockSubmitUntilComplete?: boolean }} opts
 */
export function initNavigation({ sessionId, lockSubmitUntilComplete = false }) {
  _sessionId = sessionId;
  _buildQuestionMap();
  _bindButtons();
  _goTo(0);
  if (lockSubmitUntilComplete) _updateSubmitBtn();
}

/** Mark a question as answered — call this after saving any answer. */
export function markAnswered(questionId) {
  const q = _questions.find(q => q.id === questionId);
  if (q) {
    q.answered = true;
    _updateNavBtn(q);
    _updateSubmitBtn();
    _updateReviewBtn();
  }
}

/**
 * Re-evaluate and apply the submit button's disabled state based on completion.
 * Call this from section templates after lifting an external gate (e.g. audio).
 */
export function updateSubmitBtn() {
  _updateSubmitBtn();
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

function _buildQuestionMap() {
  const blocks = [...document.querySelectorAll(".question-block[data-question-id]")];
  blocks.sort((a, b) => parseInt(a.dataset.order) - parseInt(b.dataset.order));

  _questions = blocks.map(el => ({
    id: el.dataset.questionId,
    order: parseInt(el.dataset.order),
    element: el,
    navBtn: document.querySelector(`.nav-btn[data-question-id="${el.dataset.questionId}"]`),
    flagged: false,
    answered: false,
  }));
}

function _bindButtons() {
  document.getElementById("btn-prev")?.addEventListener("click", () => _goTo(_currentIdx - 1));
  document.getElementById("btn-next")?.addEventListener("click", _handleNext);
  document.getElementById("btn-flag")?.addEventListener("click", _toggleFlag);

  _questions.forEach((q, idx) => {
    q.navBtn?.addEventListener("click", () => _goTo(idx));
  });
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function _goTo(idx) {
  if (idx < 0 || idx >= _questions.length) return;
  _currentIdx = idx;

  const q = _questions[idx];
  q.element.scrollIntoView({ behavior: "smooth", block: "nearest" });

  const prevBtn = document.getElementById("btn-prev");
  if (prevBtn) prevBtn.disabled = idx === 0;

  _updateReviewBtn();
  _renderFlagBtn(q);
}

function _handleNext() {
  if (_currentIdx === _questions.length - 1) {
    document.getElementById("btn-submit")?.scrollIntoView({ behavior: "smooth" });
    return;
  }
  _goTo(_currentIdx + 1);
}

// ---------------------------------------------------------------------------
// Submit / Review button state
// ---------------------------------------------------------------------------

function _allAnswered() {
  return _questions.every(q => q.answered);
}

function _updateReviewBtn() {
  const btn = document.getElementById("btn-next");
  if (!btn) return;
  const isLast = _currentIdx === _questions.length - 1;
  btn.textContent = isLast ? "Review ›" : "Next ›";
  if (isLast) {
    const done = _allAnswered();
    btn.disabled = !done;
    btn.classList.toggle("opacity-40", !done);
    btn.title = done ? "" : "Answer all questions to continue";
  } else {
    btn.disabled = false;
    btn.classList.remove("opacity-40");
    btn.title = "";
  }
}

function _updateSubmitBtn() {
  const btn = document.getElementById("btn-submit");
  if (!btn) return;
  const unanswered = _questions.filter(q => !q.answered).length;
  const done = unanswered === 0;
  btn.disabled = !done;
  btn.classList.toggle("opacity-50", !done);
  btn.classList.toggle("cursor-not-allowed", !done);
  btn.title = done ? "" : `${unanswered} question${unanswered === 1 ? "" : "s"} unanswered`;
}

// ---------------------------------------------------------------------------
// Flag toggle
// ---------------------------------------------------------------------------

async function _toggleFlag() {
  const q = _questions[_currentIdx];
  if (!q) return;

  q.flagged = !q.flagged;
  _updateNavBtn(q);
  _renderFlagBtn(q);

  try {
    await fetch(`/api/sessions/${_sessionId}/flag`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": _csrfToken(),
      },
      body: JSON.stringify({ question_id: q.id, flagged: q.flagged }),
    });
  } catch {
    // Non-critical: flag state is maintained client-side
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _renderFlagBtn(q) {
  const btn = document.getElementById("btn-flag");
  if (!btn) return;
  if (q.flagged) {
    btn.textContent = "⚑ Flagged";
    btn.classList.add("bg-orange-400", "text-white", "border-orange-400");
    btn.classList.remove("text-orange-500");
  } else {
    btn.textContent = "⚑ Flag";
    btn.classList.remove("bg-orange-400", "text-white", "border-orange-400");
    btn.classList.add("text-orange-500");
  }
}

function _updateNavBtn(q) {
  if (!q.navBtn) return;
  q.navBtn.classList.toggle("nav-btn--flagged", q.flagged);
  q.navBtn.classList.toggle("nav-btn--answered", q.answered && !q.flagged);
}

function _csrfToken() {
  return document.querySelector("meta[name=csrf-token]")?.content ?? "";
}
