/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#0B1120',
          card: '#1E293B',
          accent: '#0284C7',
          wind: '#06B6D4',
          actual: '#10B981',
          forecast: '#F59E0B',
          error: '#EF4444',
          border: '#334155'
        }
      }
    },
  },
  plugins: [],
}
