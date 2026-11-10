export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Vazirmatn', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#fff8eb',
          100: '#feefcb',
          200: '#f8daa0',
          300: '#edbc6a',
          400: '#e5aa4b',
          500: '#d18b23',
          600: '#946016',
          700: '#784b15',
          800: '#623e18',
          900: '#513519',
          950: '#30200e',
        },
        slate: {
          50: '#f6f7f8',
          100: '#eef1f3',
          200: '#dce2e7',
          300: '#c3ccd4',
          400: '#596977',
          500: '#596977',
          600: '#475766',
          700: '#354451',
          800: '#293641',
          850: '#24313c',
          900: '#202a35',
          925: '#19222c',
          950: '#131b24',
        }
      },
      boxShadow: {
        'bezel': 'inset 0 1px 1px 0 rgba(255, 255, 255, 0.1), 0 4px 20px -2px rgba(0, 0, 0, 0.05)',
        'bezel-dark': 'inset 0 1px 1px 0 rgba(255, 255, 255, 0.08), 0 10px 30px -5px rgba(0, 0, 0, 0.4)',
      }
    },
  },
  plugins: [],
}
