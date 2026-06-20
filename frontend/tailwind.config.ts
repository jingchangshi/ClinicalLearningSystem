import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1d2939",
        clinic: "#0f766e",
        "clinic-soft": "#ccfbf1",
        alert: "#b42318",
      },
    },
  },
  plugins: [],
};

export default config;
