import type React from 'react'

export type CardVariant = 'paper' | 'yellow' | 'cyan' | 'lime' | 'coral' | 'violet' | 'grey'
export type CardOffset = 'none' | 'top' | 'bottom' | 'left' | 'right'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
  shadowSize?: 'default' | 'lg'
  offset?: CardOffset
  children: React.ReactNode
}

const variantStyles: Record<CardVariant, string> = {
  paper: 'bg-paper text-ink',
  yellow: 'bg-yellow text-ink',
  cyan: 'bg-cyan text-ink',
  lime: 'bg-lime text-ink',
  coral: 'bg-coral text-ink',
  violet: 'bg-violet text-ink',
  grey: 'bg-grey text-ink',
}

const offsetStyles: Record<CardOffset, string> = {
  none: '',
  top: '-mt-5 sm:-mt-8 z-10',
  bottom: '-mb-5 sm:-mb-8 z-10',
  left: '-ml-4 sm:-ml-6 z-10',
  right: '-mr-4 sm:-mr-6 z-10',
}

export const Card: React.FC<CardProps> = ({
  variant = 'paper',
  shadowSize = 'default',
  offset = 'none',
  className = '',
  children,
  ...props
}) => {
  const shadowClass =
    shadowSize === 'lg'
      ? 'shadow-[10px_10px_0_var(--ink)]'
      : 'shadow-[6px_6px_0_var(--ink)]'

  return (
    <div
      className={`
        border-3 border-ink p-5 sm:p-6
        relative transition-all duration-[80ms]
        ${variantStyles[variant]}
        ${shadowClass}
        ${offsetStyles[offset]}
        ${className}
      `.trim()}
      {...props}
    >
      {children}
    </div>
  )
}

export default Card
