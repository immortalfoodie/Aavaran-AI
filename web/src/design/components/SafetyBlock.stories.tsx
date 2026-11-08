import type { Meta, StoryObj } from '@storybook/react'
import { SafetyBlock } from './SafetyBlock'

const meta: Meta<typeof SafetyBlock> = {
  title: 'NeoBrutalist/SafetyBlock',
  component: SafetyBlock,
  tags: ['autodocs'],
  argTypes: {
    title: { control: 'text' },
    advisory: { control: 'text' },
    action: { control: 'text' },
    hazardCode: { control: 'text' },
  },
}

export default meta
type Story = StoryObj<typeof SafetyBlock>

export const BotulinumInterlock: Story = {
  args: {
    title: 'PACKAGING WILL NOT SAVE THIS FOOD',
    advisory:
      'Cut potato stored at 30 °C ambient presents severe Clostridium botulinum germination and anaerobic spoilage hazards. Sealing in a low-oxygen barrier film creates a fatal microbial environment.',
    action: 'Chill below 4 °C immediately, sell unsealed within 8 hours, or cook/process.',
    hazardCode: 'BIO-BOT-01 / FSSAI SEC-16',
  },
}

export const CondensationHazard: Story = {
  args: {
    title: 'RAPID ROT / CONDENSATION HAZARD',
    advisory:
      'High respiration produce in non-perforated film will sweat inside the packaging at current ambient temperature, inducing rapid bacterial soft rot within 24 hours.',
    action: 'Select micro-perforated film or perforated woven mesh.',
    hazardCode: 'PHY-ROT-04',
  },
}
