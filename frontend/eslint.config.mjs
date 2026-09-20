import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { FlatCompat } from "@eslint/eslintrc";

/**
 * Flat ESLint config.
 *
 * `next lint` is deprecated in Next.js 15 and removed in 16, so the project uses the
 * ESLint CLI directly (see the `lint` script in package.json). `FlatCompat` keeps the
 * Next.js shareable configs working under ESLint 9's flat config format.
 */
const compat = new FlatCompat({
  baseDirectory: dirname(fileURLToPath(import.meta.url)),
});

const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default eslintConfig;
