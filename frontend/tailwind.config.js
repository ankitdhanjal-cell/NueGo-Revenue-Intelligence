import colors from 'tailwindcss/colors';

/** Warm paper, ink text, one navy accent. The grey scale is Tailwind's warm "stone" under the name slate. */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    borderRadius: { none: '0', sm: '2px', DEFAULT: '3px', md: '3px', lg: '4px', xl: '4px', full: '9999px' },
    fontFamily: {
      sans: ['"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      serif: ['Charter', '"Iowan Old Style"', '"Palatino Linotype"', 'Georgia', 'serif'],
      mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        white: '#fffdf8',
        paper: '#f5f1e8',
        slate: colors.stone,
        brand: { 50: '#ece9e0', 100: '#e0dccf', 600: '#2c3e5c', 700: '#22304a', 900: '#141c2c' },
        good: '#2f6b5a',
        bad: '#a3302b',
        ochre: { 50: '#fbf3dc', 100: '#f4e3ae', 700: '#7a5a0e', 900: '#4a3606' },
      },
    },
  },
  plugins: [],
};
