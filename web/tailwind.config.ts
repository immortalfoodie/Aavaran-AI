import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    borderRadius: {
      none: '0px',
      DEFAULT: '0px',
      sm: '0px',
      md: '0px',
      lg: '0px',
      xl: '0px',
      '2xl': '0px',
      '3xl': '0px',
      full: '0px',
    },
    extend: {
      colors: {
        paper: 'var(--paper)',
        ink: 'var(--ink)',
        yellow: 'var(--yellow)',
        cyan: 'var(--cyan)',
        lime: 'var(--lime)',
        coral: 'var(--coral)',
        violet: 'var(--violet)',
        grey: 'var(--grey)',
      },
      borderColor: {
        ink: 'var(--ink)',
        paper: 'var(--paper)',
        yellow: 'var(--yellow)',
        cyan: 'var(--cyan)',
        lime: 'var(--lime)',
        coral: 'var(--coral)',
        violet: 'var(--violet)',
        grey: 'var(--grey)',
      },
      borderWidth: {
        '2': '2px',
        '3': '3px',
        '6': '6px',
      },
      boxShadow: {
        brut: '6px 6px 0 var(--ink)',
        'brut-lg': '10px 10px 0 var(--ink)',
        'brut-sm': '3px 3px 0 var(--ink)',
        'brut-hover': '8px 8px 0 var(--ink)',
        'brut-active': '2px 2px 0 var(--ink)',
      },
      fontFamily: {
        display: ['"Archivo Black"', 'sans-serif'],
        body: ['"Space Grotesk"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      transitionTimingFunction: {
        linear: 'linear',
      },
      transitionDuration: {
        snap: '80ms',
      },
    },
  },
  plugins: [],
}

export default config
