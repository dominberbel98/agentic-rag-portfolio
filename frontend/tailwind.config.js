/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "on-tertiary-container": "#004d57",
        primary: "#9cff93",
        outline: "#767555",
        "on-primary-container": "#005a10",
        "primary-dim": "#00ec3b",
        "on-secondary-container": "#fff6ef",
        "tertiary-dim": "#00d4ec",
        "inverse-primary": "#006f16",
        "secondary-dim": "#eba300",
        "tertiary-fixed-dim": "#00d4ec",
        "on-secondary": "#503500",
        "error-container": "#b92902",
        "surface-bright": "#2c2c2c",
        "surface-container-low": "#131313",
        "on-primary-fixed": "#00440a",
        "tertiary-container": "#00e3fd",
        "on-tertiary-fixed": "#003840",
        "on-surface": "#ffffff",
        "inverse-on-surface": "#565555",
        "tertiary-fixed": "#00e3fd",
        "inverse-surface": "#fcf9f8",
        "primary-container": "#00fc40",
        "outline-variant": "#484847",
        "on-primary": "#006413",
        "on-primary-fixed-variant": "#006513",
        "primary-fixed": "#00fc40",
        "secondary-container": "#7f5600",
        "surface-container-lowest": "#000000",
        tertiary: "#81ecff",
        "primary-fixed-dim": "#00ec3b",
        "error-dim": "#d53d18",
        "on-background": "#ffffff",
        "surface-tint": "#9cff93",
        "surface-container-high": "#201f1f",
        "surface-container-highest": "#262626",
        "on-error": "#450900",
        "secondary-fixed-dim": "#ffb62d",
        "on-tertiary-fixed-variant": "#005762",
        "on-secondary-fixed-variant": "#6d4a00",
        "surface-dim": "#0e0e0e",
        error: "#ff7351",
        surface: "#0e0e0e",
        "on-tertiary": "#005762",
        "on-secondary-fixed": "#482f00",
        secondary: "#fcaf00",
        "secondary-fixed": "#ffc972",
        "surface-container": "#1a1919",
        "on-error-container": "#ffd2c8",
        "surface-variant": "#262626",
        "on-surface-variant": "#adaaaa",
        background: "#0e0e0e"
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem"
      },
      fontFamily: {
        headline: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Space Grotesk", "sans-serif"]
      }
    }
  },
  plugins: []
};
