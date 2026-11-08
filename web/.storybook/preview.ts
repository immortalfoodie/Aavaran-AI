import type { Preview } from '@storybook/react'
import '../src/design/tokens.css'
import '../src/index.css'

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'paper',
      values: [
        { name: 'paper', value: '#FFFDF2' },
        { name: 'dark', value: '#121212' },
      ],
    },
  },
}

export default preview
