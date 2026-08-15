import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0c0f",
        panel: "#15171c",
        border: "#262a33",
        accent: "#f2b544",
      },
    },
  },
  plugins: [],
};

export default config;
