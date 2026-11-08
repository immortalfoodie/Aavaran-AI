import type { Meta, StoryObj } from '@storybook/react'
import { Stat } from './Stat'

const meta: Meta<typeof Stat> = {
  title: 'NeoBrutalist/Stat',
  component: Stat,
  tags: ['autodocs'],
  argTypes: {
    value: { control: 'text' },
    unit: { control: 'text' },
    label: { control: 'text' },
    helper: { control: 'text' },
  },
}

export default meta
type Story = StoryObj<typeof Stat>

export const ShelfLife: Story = {
  args: {
    value: '42',
    unit: 'DAYS',
    label: 'PREDICTED SHELF LIFE',
    helper: 'Safe floor at 12 °C / 85% RH (0.75x safety factor)',
  },
}

export const CostPerPack: Story = {
  args: {
    value: '₹3.40',
    unit: '/PACK',
    label: 'UNIT COST',
    helper: 'Including EPR Category III liability',
  },
}

export const PostHarvestLoss: Story = {
  args: {
    value: '15.05',
    unit: '%',
    label: 'POST-HARVEST LOSS BASELINE',
    helper: 'MoFPI / NABCONS 2022 Guava benchmark',
  },
}
