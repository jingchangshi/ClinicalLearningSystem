import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default [
  {
    // `.next*` also covers a disposable build written by NEXT_DIST_DIR.
    ignores: [".next/**", ".next*/**", "node_modules/**", "next-env.d.ts"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
];
