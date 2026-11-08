import type { Meta, StoryObj } from '@storybook/react'
import { SourceBadge } from './SourceBadge'

const meta: Meta<typeof SourceBadge> = {
  title: 'NeoBrutalist/SourceBadge',
  component: SourceBadge,
  tags: ['autodocs'],
  argTypes: {
    source: { control: 'text' },
  },
}

export default meta
type Story = StoryObj<typeof SourceBadge>

export const OfficialHandbook: Story = {
  args: {
    source: 'USDA AH-66',
    citation: {
      source: 'USDA AH-66',
      title: 'The Commercial Storage of Fruits, Vegetables, and Florist and Nursery Stocks',
      clause: 'Table 2, Solanum tuberosum respiration & chilling injury thresholds',
      year: 2016,
    },
  },
}

export const LegalCitation: Story = {
  args: {
    source: 'FSSAI SCH-I',
    citation: {
      source: 'FSSAI SCH-I',
      title: 'Food Safety and Standards (Packaging) Regulations, Schedule I',
      clause: 'Schedule I, Permitted food-contact polymers for root vegetables',
      year: 2018,
    },
  },
}

export const UserDirectInput: Story = {
  args: {
    source: 'USER INPUT',
    citation: {
      source: 'USER INPUT',
      title: 'Direct farmer specification in Maharashtra field survey',
      year: 2026,
    },
  },
}
