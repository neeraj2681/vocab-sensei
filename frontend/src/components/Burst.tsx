const PIECES = 36
const COLORS = ['var(--accent)', 'var(--flame)', '#f5c518', '#4aa3ff', 'var(--bad)']

/** A one-off burst of confetti from the middle of the screen (skipped with reduced motion). */
export function Burst() {
  return (
    <div className="burst" aria-hidden="true">
      {Array.from({ length: PIECES }, (_, i) => {
        const angle = (Math.PI * 2 * i) / PIECES
        const reach = 140 + ((i * 37) % 120) // varied but stable between renders
        return (
          <span
            key={i}
            style={
              {
                background: COLORS[i % COLORS.length],
                '--x': `${String(Math.round(Math.cos(angle) * reach))}px`,
                '--y': `${String(Math.round(Math.sin(angle) * reach - 60))}px`,
                '--r': `${String((i * 97) % 720)}deg`,
              } as React.CSSProperties
            }
          />
        )
      })}
    </div>
  )
}
