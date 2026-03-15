/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        yc: { orange: '#f26522' },
      },
    },
  },
  plugins: [],
}
