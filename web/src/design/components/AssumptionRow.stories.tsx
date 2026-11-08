import type { Meta, StoryObj } from '@storybook/react'
import { AssumptionRow } from './AssumptionRow'

const meta: Meta<typeof AssumptionRow> = {
  title: 'NeoBrutalist/AssumptionRow',
  component: AssumptionRow,
  tags: ['autodocs'],
  argTypes: {
    fieldName: { control: 'text' },
    value: { control: 'text' },
    unit: { control: 'text' },
    source: { control: 'text' },
    confidence: { control: { type: 'range', min: 0, max: 10, step: 1 } },
  },
}

export default meta
type Story = StoryObj<typeof AssumptionRow>

export const TemperatureAssumption: Story = {
  args: {
    fieldName: 'STORAGE TEMPERATURE',
    value: '28.0',
    unit: '°C',
    source: 'GEO CLIMATOLOGY',
    citation: {
      source: 'GEO CLIMATOLOGY',
      title: 'Mumbai Sept historical 95th percentile ambient peak',
      year: 2026,
    },
    confidence: 6,
    isExplicit: false,
    onEdit: () => alert('Edit temperature triggered'),
  },
}

export const RespirationRateExpert: Story = {
  args: {
    fieldName: 'RESPIRATION RATE (R_O2)',
    value: '24.5',
    unit: 'mg/kg·h',
    source: 'USDA AH-66',
    citation: {
      source: 'USDA AH-66',
      title: 'Handbook 66 Chapter on Solanum tuberosum respiration at 20°C',
    },
    confidence: 9,
    isExplicit: false,
    onEdit: () => alert('Edit respiration rate triggered'),
  },
}

export const UserVerifiedWaterActivity: Story = {
  args: {
    fieldName: 'INITIAL WATER ACTIVITY (aw)',
    value: '0.62',
    unit: 'aw',
    source: 'USER INPUT',
    citation: {
      source: 'USER INPUT',
      title: 'Lab meter measurement confirmed by food technologist',
    },
    confidence: 10,
    isExplicit: true,
    onEdit: () => alert('Edit water activity triggered'),
  },
}
