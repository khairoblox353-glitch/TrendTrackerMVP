/** PostCSS pipeline: Tailwind first, then vendor prefixes. */
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
