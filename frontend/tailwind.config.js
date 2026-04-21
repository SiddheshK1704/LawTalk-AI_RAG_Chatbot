/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./chat.html",
    "./js/**/*.js",
    "./src/**/*.css",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#08111f",
        "ink-soft": "#0f1b30",
        paper: "#f5efe2",
        gold: "#f6bb42",
        "gold-soft": "#ffd06b",
        mint: "#6ae3b9",
      },
      fontFamily: {
        sans: ["Manrope", "sans-serif"],
        display: ["Space Grotesk", "sans-serif"],
      },
    },
  },
  plugins: [],
};
