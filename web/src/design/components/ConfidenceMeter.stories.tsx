import type { Meta, StoryObj } from '@storybook/react'
import { ConfidenceMeter } from './ConfidenceMeter'

const meta: Meta<typeof ConfidenceMeter> = {
  title: 'NeoBrutalist/ConfidenceMeter',
  component: ConfidenceMeter,
  tags: ['autodocs'],
  argTypes: {
    score: {
      control: { type: 'range', min: 0, max: 10, step: 1 },
    },
    label: { control: 'text' },
    showNumeric: { control: 'boolean' },
  },
}

export default meta
type Story = StoryObj<typeof ConfidenceMeter>

export const LowConfidence: Story = {
  args: {
    score: 2,
    showNumeric: true,
  },
}

export const FairConfidence: Story = {
  args: {
    score: 5,
    showNumeric: true,
  },
}

export const GoodConfidence: Story = {
  args: {
    score: 8,
    showNumeric: true,
  },
}

export const HighConfidence: Story = {
  args: {
    score: 10,
    showNumeric: true,
  },
}
