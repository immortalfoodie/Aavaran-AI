import type React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SpecTable } from './SpecTable'

interface MaterialSpec {
  [key: string]: unknown
  material: string
  thickness: string
  otr: string
  wvtr: string
  cost: string
  recyclability: string
}

const meta: Meta<typeof SpecTable<MaterialSpec>> = {
  title: 'NeoBrutalist/SpecTable',
  component: SpecTable as unknown as React.FC,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof SpecTable<MaterialSpec>>

const sampleData: MaterialSpec[] = [
  {
    material: 'LDPE (Mono-material)',
    thickness: '45 µm',
    otr: '3,200 cc/m²·d',
    wvtr: '14.2 g/m²·d',
    cost: '₹1.85',
    recyclability: '100% CAT-I',
  },
  {
    material: 'BOPP / Metallized CPP',
    thickness: '38 µm',
    otr: '45 cc/m²·d',
    wvtr: '1.2 g/m²·d',
    cost: '₹2.95',
    recyclability: 'MULTI-LAYER',
  },
  {
    material: 'PET / AlOx / PE',
    thickness: '52 µm',
    otr: '1.2 cc/m²·d',
    wvtr: '0.8 g/m²·d',
    cost: '₹4.60',
    recyclability: 'BARRIER RETORT',
  },
  {
    material: 'Cellulose / PLA Compostable',
    thickness: '40 µm',
    otr: '120 cc/m²·d',
    wvtr: '28.0 g/m²·d',
    cost: '₹5.20',
    recyclability: 'BIO COMPOST',
  },
]

export const BarrierSpecSheet: Story = {
  args: {
    caption: 'CANDIDATE MATERIAL COMPARISON MATRIX',
    columns: [
      { key: 'material', header: 'STRUCTURE NAME', isNumeric: false },
      { key: 'thickness', header: 'GAUGE', isNumeric: true },
      { key: 'otr', header: 'OTR (23°C/0% RH)', isNumeric: true },
      { key: 'wvtr', header: 'WVTR (38°C/90% RH)', isNumeric: true },
      { key: 'cost', header: 'UNIT ₹/PACK', isNumeric: true },
      { key: 'recyclability', header: 'EPR CLASS', isNumeric: false },
    ],
    data: sampleData,
  },
}
