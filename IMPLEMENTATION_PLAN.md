# Implementation Plan: Intsight Education IELTS Simulation Platform

## 1. Project Overview
The objective is to develop a high-fidelity Computer-Delivered (CD) IELTS simulation platform that replicates the official testing environment. The platform will serve both as a training tool for Intsight Education students and a diagnostic tool for external users to measure exam readiness.

---

## 2. Core Functional Modules

### A. Exam Interface (The "Simulation Engine")
To ensure authenticity, the UI must mirror the official CD-IELTS software:
* **Reading Interface:** Split-screen view (Passage Left / Questions Right) with independent scrolling.
* **Interaction Tools:** * Right-click to **Highlight** and **Add Notes**.
    * Bottom **Navigation Bar** with "Review" flag functionality.
* **Time Management:** Central countdown timer with visual alerts at 10 and 5 minutes.
* **Pacing Enforcement:** Strict 2-minute checking time for Listening (no 10-minute transfer time).

### B. Section-Specific Technicals
* **Listening:** One-time playback only; disabled seek bars; hardware volume calibration step.
* **Reading:** Standardized font and column formatting mimicking academic papers.
* **Writing:** Live word count (Task 1 & 2), auto-save every 10 seconds, and support for standard keyboard shortcuts (Ctrl+C/V/Z).
* **Speaking:** * Simulated Video-Call Interface.
    * **AI Virtual Examiner:** Dynamic follow-up questions using STT (Speech-to-Text) and LLM-driven logic.

---

## 3. Evaluation & AI Analytics
The platform's primary value proposition is its diagnostic accuracy.

* **AI Band Estimator:** Scored based on official **IELTS Public Band Descriptors**:
    * *Writing:* Task Response, Cohesion/Coherence, Lexical Resource, Grammatical Range.
    * *Speaking:* Fluency, Pronunciation, Grammar, Vocabulary.
* **Diagnostic Heatmaps:** Visual identification of weak question types (e.g., "Matching Headings" vs. "True/False/Not Given").
* **Sentence Complexity Analysis:** Highlighting simple vs. complex structures to guide students toward Band 7+ criteria.

---

## 4. Administrative & Teacher Features
Designed specifically for the Intsight Education faculty:
* **Student Progress Dashboard:** Track score trends and plateau points.
* **Manual Grading Interface:** Ability for teachers to override AI scores or provide personalized voice/text feedback.
* **Readiness Indicator:** A data-driven "Go/No-Go" status for students based on their last 5 mock performances.

---

## 5. Technical Architecture & Security
* **Deployment:** Web-based application optimized for Desktop/Laptop (Simulation mode locked on mobile).
* **Integrity:** Lightweight **Lockdown Browser** functionality to prevent the use of external AI or translation tools during the test.
* **Audio Performance:** Pre-caching audio files to prevent buffering mid-exam.
* **Data Resiliency:** Local-first storage (IndexedDB) during the exam to protect against internet disconnects.

---

## 6. Development Roadmap

| Phase | Milestone | Focus |
| :--- | :--- | :--- |
| **Phase 1** | MVP (Minimum Viable Product) | CD-IELTS UI, Reading & Listening modules. |
| **Phase 2** | AI Integration | Automated Writing scoring and Diagnostic feedback. |
| **Phase 3** | Speaking & Admin | Video-call simulation and Teacher Dashboard. |
| **Phase 4** | Security & Launch | Lockdown features, load testing, and official rollout. |

---

## 7. Strategic Goal
By 2026, Intsight Education will leverage this platform to ensure that no student enters a real IELTS center without first achieving their target score at least twice within the simulation environment, significantly increasing the center's pass rates and reputation.
