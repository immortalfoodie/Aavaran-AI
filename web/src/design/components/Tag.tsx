import type React from 'react'

export type TagVariant = 'paper' | 'yellow' | 'cyan' | 'lime' | 'coral' | 'violet' | 'grey'

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: TagVariant
  label: string
  icon?: React.ReactNode
}

const variantStyles: Record<TagVariant, string> = {
  paper: 'bg-paper text-ink',
  yellow: 'bg-yellow text-ink',
  cyan: 'bg-cyan text-ink',
  lime: 'bg-lime text-ink',
  coral: 'bg-coral text-ink',
  violet: 'bg-violet text-ink',
  grey: 'bg-grey text-ink',
}

export const Tag: React.FC<TagProps> = ({
  variant = 'paper',
  label,
  icon,
  className = '',
  ...props
}) => {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5
        border-2 border-ink
        font-mono uppercase text-xs font-bold
        px-2 py-0.5 select-none
        ${variantStyles[variant]}
        ${className}
      `.trim()}
      {...props}
    >
      {icon && <span className="inline-flex shrink-0 items-center justify-center">{icon}</span>}
      <span>{label}</span>
    </span>
  )
}

export default Tag
