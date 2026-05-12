/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Official CD-IELTS color palette
        "ielts-blue":   "#003B71",
        "ielts-button": "#0071BC",
        "ielts-border": "#CCCCCC",
        "exam-bg":      "#F5F5F5",
        "highlight-yellow": "#FFE082",
        "highlight-pink":   "#F48FB1",
        "highlight-blue":   "#90CAF9",
      },
      fontFamily: {
        serif: ["Noto Serif", "Georgia", "serif"],
        sans:  ["Inter", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
