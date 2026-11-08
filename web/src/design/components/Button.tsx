import type React from 'react'

export type ButtonVariant = 'primary' | 'info' | 'success' | 'danger' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: React.ReactNode
  /** Required accessible/visible text label. Icon-only controls are strictly prohibited. */
  label: string
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: 'bg-yellow text-ink border-ink hover:bg-yellow',
  info: 'bg-cyan text-ink border-ink hover:bg-cyan',
  success: 'bg-lime text-ink border-ink hover:bg-lime',
  danger: 'bg-coral text-ink border-ink hover:bg-coral',
  ghost: 'bg-transparent text-ink border-ink hover:bg-paper',
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'text-xs py-1.5 px-3 tracking-wider',
  md: 'text-sm py-2.5 px-5 tracking-wider',
  lg: 'text-base py-3.5 px-6 tracking-wide',
  xl: 'text-lg py-4 px-8 min-h-[64px] tracking-wide', // Kisan mode: calloused thumb & cracked screen floor
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  icon,
  label,
  children,
  className = '',
  disabled = false,
  ...props
}) => {
  return (
    <button
      disabled={disabled}
      className={`
        inline-flex items-center justify-center gap-2.5
        font-display uppercase select-none cursor-pointer
        border-3 border-ink
        transition-[transform,box-shadow] duration-[80ms] ease-linear
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${
          disabled
            ? 'opacity-60 cursor-not-allowed bg-grey shadow-none'
            : 'shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[8px_8px_0_var(--ink)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-[2px_2px_0_var(--ink)]'
        }
        ${className}
      `.trim()}
      {...props}
    >
      {icon && <span className="inline-flex shrink-0 items-center justify-center">{icon}</span>}
      <span>{label || children}</span>
    </button>
  )
}

export default Button
