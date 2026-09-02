export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        terminal: {
          bg: "#0b1020",
          panel: "#121a2f",
          line: "#1e2a44",
          accent: "#3ee0b4",
          warn: "#f5c542",
          danger: "#ff5d73",
          muted: "#8aa0c2",
        },
      },
    },
  },
  plugins: [],
};
