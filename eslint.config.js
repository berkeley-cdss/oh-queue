import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["oh_queue", "venv", "node_modules", "migrations", "tests"] },
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
    plugins: { "react-hooks": reactHooks },
    // Only the classic hooks rules: the React Compiler rules in the recommended set
    // flag patterns throughout these older components.
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    files: ["**/*.ts"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, prettier],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
  }
);
