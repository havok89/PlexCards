/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          500: '#e5a00d',
          600: '#cc8e0c',
          700: '#b27a07'
        },
        dark: {
          800: '#1e2026',
          850: '#181a1f',
          900: '#121417',
          950: '#0b0c0e'
        }
      }
    },
  },
  plugins: [],
}
