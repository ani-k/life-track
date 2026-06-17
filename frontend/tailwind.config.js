/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        olive: {
          50:  '#f5f5ef',
          100: '#e8e8d8',
          200: '#d1d1b0',
          300: '#b9ba88',
          400: '#a2a360',
          500: '#84855c',
          600: '#6a6b4a',
          700: '#505137',
          800: '#373824',
          900: '#1f2012',
          950: '#0f1009',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        node: '0 2px 8px 0 rgba(80,81,55,0.12), 0 0 0 1px rgba(80,81,55,0.08)',
        'node-selected': '0 4px 16px 0 rgba(80,81,55,0.22), 0 0 0 2px #84855c',
      },
    },
  },
  plugins: [],
}
