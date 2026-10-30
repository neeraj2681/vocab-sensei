import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { HistoryPoint } from '../../api/quiz'
import { formatWhen } from './format'

/** Value first, details after: the reader already knows which line this is. */
function ScoreTooltip({ active, payload }: TooltipContentProps) {
  const point = payload[0]?.payload as HistoryPoint | undefined
  if (!active || !point) return null
  return (
    <div className="chart-tooltip">
      <strong>{point.total.toLocaleString()} points</strong>
      <span>
        Answer #{point.number.toLocaleString()} · {point.correct ? '✓ right' : '✗ wrong'}
      </span>
      <span className="muted">{formatWhen(point.answered_at)}</span>
    </div>
  )
}

/** Lifetime points after every answer since the first one. */
export function ScoreChart({ history }: { history: HistoryPoint[] }) {
  return (
    <figure
      className="score-chart"
      role="img"
      aria-label={`Score after each of your ${String(history.length)} answers`}
    >
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={history} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
          <XAxis
            dataKey="number"
            type="number"
            domain={['dataMin', 'dataMax']}
            allowDecimals={false}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            label={{
              value: 'Answer #',
              position: 'insideBottomRight',
              offset: -4,
              fill: 'var(--muted)',
              fontSize: 12,
            }}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={48}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
          />
          <Tooltip
            content={ScoreTooltip}
            cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="total"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: 'var(--bg)', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}
