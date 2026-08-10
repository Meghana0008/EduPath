import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          50: "#f0f9fa",
          100: "#d9f0f3",
          200: "#b7e1e8",
          300: "#85cad6",
          400: "#4fa9bc",
          500: "#348ea3",
          600: "#2d7289",
          700: "#295d70",
          800: "#284e5d",
          900: "#25424f",
          950: "#132a35",
        },
        sand: {
          50: "#faf8f4",
          100: "#f3ede3",
          200: "#e6d9c4",
          300: "#d4bf9a",
          400: "#c4a574",
          500: "#b68f5a",
          600: "#a87a4d",
          700: "#8c6242",
          800: "#73503a",
          900: "#5f4232",
        },
        gold: {
          400: "#d4a853",
          500: "#c4922e",
          600: "#a87724",
        },
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-dm-sans)", "system-ui", "sans-serif"],
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out forwards",
        "slide-up": "slideUp 0.4s ease-out forwards",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      backgroundImage: {
        "ocean-gradient":
          "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(52, 142, 163, 0.15), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(196, 146, 46, 0.08), transparent)",
        "grid-pattern":
          "linear-gradient(rgba(45, 114, 137, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(45, 114, 137, 0.03) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "32px 32px",
      },
    },
  },
  plugins: [],
};

export default config;
