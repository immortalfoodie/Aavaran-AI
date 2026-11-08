import type React from 'react'

export interface SpecTableColumn<T> {
  key: string
  header: string
  isNumeric?: boolean
  render?: (row: T) => React.ReactNode
}

export interface SpecTableProps<T> {
  columns: SpecTableColumn<T>[]
  data: T[]
  caption?: string
  className?: string
}

export function SpecTable<T extends Record<string, unknown>>({
  columns,
  data,
  caption,
  className = '',
}: SpecTableProps<T>): React.ReactElement {
  return (
    <div
      className={`border-3 border-ink overflow-x-auto bg-paper shadow-[6px_6px_0_var(--ink)] ${className}`.trim()}
    >
      <table className="w-full border-collapse text-left select-none min-w-[500px]">
        {caption && (
          <caption className="font-display uppercase text-sm p-3 bg-paper border-b-2 border-ink text-left text-ink tracking-wider">
            {caption}
          </caption>
        )}
        <thead>
          <tr className="bg-ink text-paper border-b-2 border-ink">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`
                  p-3 font-display uppercase text-xs sm:text-sm tracking-wider
                  ${col.isNumeric ? 'text-right' : 'text-left'}
                `}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => {
            const isStripe = rowIndex % 2 === 1
            return (
              <tr
                key={rowIndex}
                className={`
                  border-b-2 border-ink transition-colors duration-[80ms]
                  ${isStripe ? 'bg-grey/60' : 'bg-paper'}
                  hover:bg-yellow/20
                `}
              >
                {columns.map((col) => {
                  const val = row[col.key]
                  return (
                    <td
                      key={col.key}
                      className={`
                        p-3 text-sm text-ink
                        ${
                          col.isNumeric
                            ? 'font-mono text-right font-semibold'
                            : 'font-body font-medium'
                        }
                      `}
                    >
                      {col.render ? col.render(row) : (val as React.ReactNode)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default SpecTable
