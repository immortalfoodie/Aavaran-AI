import type { Meta, StoryObj } from '@storybook/react'
import { Card } from './Card'

const meta: Meta<typeof Card> = {
  title: 'NeoBrutalist/Card',
  component: Card,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['paper', 'yellow', 'cyan', 'lime', 'coral', 'violet', 'grey'],
    },
    shadowSize: {
      control: 'select',
      options: ['default', 'lg'],
    },
    offset: {
      control: 'select',
      options: ['none', 'top', 'bottom', 'left', 'right'],
    },
  },
}

export default meta
type Story = StoryObj<typeof Card>

export const DefaultPaper: Story = {
  args: {
    variant: 'paper',
    children: (
      <div>
        <h3 className="font-display text-xl mb-2">COMMODITY PROFILE</h3>
        <p className="font-body text-sm leading-relaxed">
          Storage baseline: 12 °C, 85–90% RH. Moisture sorption follows GAB isotherm model with safe water activity aw ≤ 0.65.
        </p>
      </div>
    ),
  },
}

export const YellowFill: Story = {
  args: {
    variant: 'yellow',
    children: (
      <div>
        <h3 className="font-display text-xl mb-2">PRIMARY ACTION CARD</h3>
        <p className="font-body text-sm">
          Recommended primary barrier solution for perishable potato consignment.
        </p>
      </div>
    ),
  },
}

export const OverlappingOffset: Story = {
  render: () => (
    <div className="p-8 max-w-lg">
      <Card variant="paper" className="z-0">
        <h3 className="font-display text-lg mb-1">BASE LAYER: JUTE LINER</h3>
        <p className="font-body text-xs">Standard woven breathable sack</p>
      </Card>
      <Card variant="yellow" offset="top">
        <h3 className="font-display text-lg mb-1">OVERLAY: MICRO-PERFORATED LDPE</h3>
        <p className="font-body text-xs">Laser pinholes 80µm, 12 holes/pack, maintains equilibrium O₂ &gt; 2%</p>
      </Card>
    </div>
  ),
}
