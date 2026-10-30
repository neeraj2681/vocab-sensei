const WIDTH = 120
const HEIGHT = 32

/** A tiny line of recent score totals; rises with right answers, dips with wrong ones. */
export function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null
  const min = Math.min(...values)
  const range = Math.max(...values) - min || 1
  const points = values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * WIDTH
      const y = HEIGHT - 2 - ((value - min) / range) * (HEIGHT - 4)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const rising = (values.at(-1) ?? 0) >= (values.at(0) ?? 0)

  return (
    <svg
      className={`sparkline sparkline--${rising ? 'up' : 'down'}`}
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
      role="img"
      aria-label={`Score over your last ${String(values.length - 1)} answers`}
    >
      <polyline points={points} fill="none" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}
