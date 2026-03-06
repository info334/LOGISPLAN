import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#e8f4f8",
          100: "#b8dde8",
          200: "#88c6d8",
          300: "#58afc8",
          400: "#2898b8",
          500: "#1F4E79",
          600: "#1a4267",
          700: "#153655",
          800: "#102a43",
          900: "#0b1e31",
        },
      },
    },
  },
  plugins: [],
};

export default config;
