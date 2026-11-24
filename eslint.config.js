import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// As in sections (eslint.config.js), plus plain JavaScript: only state.ts is TypeScript yet.
const react = {
  plugins: {
    "react-hooks": reactHooks,
    "react-refresh": reactRefresh,
  },
  rules: {
    ...reactHooks.configs.recommended.rules,
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
  },
};

export default tseslint.config(
  { ignores: ["oh_queue", "venv", "node_modules"] },
  {
    files: ["**/*.{js,jsx}"],
    extends: [js.configs.recommended, prettier],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        ...globals.browser,
        // jQuery and its Bootstrap 3 plugins still come from the CDN
        // (oh_queue/templates/default.html), until the move to Bootstrap 5.
        $: "readonly",
      },
    },
    ...react,
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, prettier],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    ...react,
  },
);
