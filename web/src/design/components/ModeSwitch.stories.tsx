import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { ModeSwitch, type AppMode } from './ModeSwitch'

const meta: Meta<typeof ModeSwitch> = {
  title: 'NeoBrutalist/ModeSwitch',
  component: ModeSwitch,
  tags: ['autodocs'],
  argTypes: {
    activeMode: {
      control: 'select',
      options: ['kisan', 'business', 'expert'],
    },
  },
}

export default meta
type Story = StoryObj<typeof ModeSwitch>

function InteractiveModeSwitchDemo() {
  const [mode, setMode] = useState<AppMode>('kisan')
  return (
    <div className="p-6 bg-paper border-3 border-ink max-w-xl">
      <div className="mb-4">
        <ModeSwitch activeMode={mode} onChange={setMode} />
      </div>
      <div className="p-4 border-2 border-ink bg-grey/20">
        <p className="font-mono text-sm">
          Current Active Mode: <strong className="font-display uppercase">{mode}</strong>
        </p>
      </div>
    </div>
  )
}

export const InteractiveSwitch: Story = {
  render: () => <InteractiveModeSwitchDemo />,
}

export const KisanActive: Story = {
  args: {
    activeMode: 'kisan',
    onChange: () => {},
  },
}

export const BusinessActive: Story = {
  args: {
    activeMode: 'business',
    onChange: () => {},
  },
}

export const ExpertActive: Story = {
  args: {
    activeMode: 'expert',
    onChange: () => {},
  },
}
