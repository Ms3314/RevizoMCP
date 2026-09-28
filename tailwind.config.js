/** Tailwind build config for Revizo's web dashboard.
 *  Rebuild with:  npx tailwindcss@3.4.17 -c tailwind.config.js -i app/web/styles.css -o public/app.css --minify
 *  Only needed when template classes change — public/app.css is committed. */
module.exports = {
  content: ["app/web/templates/**/*"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
};
