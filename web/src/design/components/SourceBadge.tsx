import type React from 'react'

export interface CitationInfo {
  id?: string
  source: string
  title?: string
  url?: string
  clause?: string
  year?: number | string
}

export interface SourceBadgeProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  source: string
  citation?: CitationInfo
  onOpenCitation?: (citation: CitationInfo) => void
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({
  source,
  citation,
  onOpenCitation,
  className = '',
  ...props
}) => {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    props.onClick?.(e)
    if (onOpenCitation) {
      onOpenCitation(citation || { source })
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`
        inline-flex items-center gap-1.5
        border-2 border-ink bg-paper text-ink
        hover:bg-yellow active:bg-yellow
        font-mono uppercase text-xs font-bold
        px-2.5 py-1 cursor-pointer select-none
        shadow-[2px_2px_0_var(--ink)]
        hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-[3px_3px_0_var(--ink)]
        active:translate-x-[2px] active:translate-y-[2px] active:shadow-none
        transition-[transform,box-shadow,background-color] duration-[80ms] ease-linear
        ${className}
      `.trim()}
      title={citation?.title || `Citation source: ${source}`}
      {...props}
    >
      <span className="font-display text-[10px] bg-ink text-paper px-1 py-0.2">
        SRC
      </span>
      <span>{source}</span>
      <span className="text-[10px]" aria-hidden="true">↗</span>
    </button>
  )
}

export default SourceBadge
