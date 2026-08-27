import globals from "globals";

export default [
  {
    files: ["src/**/*.{js,jsx}"],
    ignores: ["**/*.test.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser },
    },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^(_|[A-Z])" }],
    },
  },
];
