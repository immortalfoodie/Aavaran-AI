import type { Meta, StoryObj } from '@storybook/react'
import { Tag } from './Tag'

const meta: Meta<typeof Tag> = {
  title: 'NeoBrutalist/Tag',
  component: Tag,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['paper', 'yellow', 'cyan', 'lime', 'coral', 'violet', 'grey'],
    },
    label: { control: 'text' },
  },
}

export default meta
type Story = StoryObj<typeof Tag>

export const DefaultPaper: Story = {
  args: {
    variant: 'paper',
    label: 'FSSAI SCH-I',
  },
}

export const EcoSafe: Story = {
  args: {
    variant: 'lime',
    label: '✓ MONO-MATERIAL PP',
  },
}

export const Regulated: Story = {
  args: {
    variant: 'yellow',
    label: 'PWM 2022 CAT-III',
  },
}

export const DangerTag: Story = {
  args: {
    variant: 'coral',
    label: '⚠ RECYCLED PLASTIC BANNED',
  },
}

export const InfoTag: Story = {
  args: {
    variant: 'cyan',
    label: 'ASTM F1249',
  },
}
