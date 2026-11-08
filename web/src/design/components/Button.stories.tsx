import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'NeoBrutalist/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'info', 'success', 'danger', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg', 'xl'],
    },
    disabled: {
      control: 'boolean',
    },
  },
}

export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: {
    variant: 'primary',
    size: 'md',
    label: 'SUBMIT SPEC',
  },
}

export const Info: Story = {
  args: {
    variant: 'info',
    size: 'md',
    label: 'BUSINESS RFQ',
  },
}

export const Success: Story = {
  args: {
    variant: 'success',
    size: 'md',
    label: 'APPROVE MATERIAL',
  },
}

export const Danger: Story = {
  args: {
    variant: 'danger',
    size: 'md',
    label: 'ABORT CALCULATION',
  },
}

export const Ghost: Story = {
  args: {
    variant: 'ghost',
    size: 'md',
    label: 'CANCEL',
  },
}

export const KisanModeXl: Story = {
  args: {
    variant: 'primary',
    size: 'xl',
    label: 'KISAAN SUBMIT (64PX)',
  },
}

export const WithPairedIcon: Story = {
  args: {
    variant: 'primary',
    size: 'lg',
    label: 'CALCULATE SHELF LIFE',
    icon: <span>⚡</span>,
  },
}
