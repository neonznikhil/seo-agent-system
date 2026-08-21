/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F4EF",
        stone: "#EDEBE6",
        ink: "#111111",
        muted: "#6B6B6B",
        line: "#D1CCC4",
        accent: "#FF4D12",
      },
      fontFamily: {
        dot: ['"DotGothic16"', "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
    },
  },
  plugins: [],
};
