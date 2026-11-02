import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Rectangle,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { Day } from '../../api/quiz'

interface DayBar {
  label: string // short weekday, "Today" for the last
  name: string // the long weekday, for the tooltip and the table
  points: number
  answers: number
}

function signed(points: number): string {
  return points > 0 ? `+${points.toLocaleString()}` : points.toLocaleString()
}

function DayTooltip({ active, payload }: TooltipContentProps) {
  const bar = payload[0]?.payload as DayBar | undefined
  if (!active || !bar) return null
  return (
    <div className="chart-tooltip">
      <strong>{signed(bar.points)} points</strong>
      <span className="muted">
        {bar.name} · {bar.answers} {bar.answers === 1 ? 'answer' : 'answers'}
      </span>
    </div>
  )
}

/** The score earned on each of the last seven days; a wrong answer costs points, so a day can dip. */
export function WeekChart({ days }: { days: Day[] }) {
  const bars: DayBar[] = days.map((day, i) => {
    const local = new Date(`${day.date}T12:00:00`)
    const isToday = i === days.length - 1
    return {
      label: isToday ? 'Today' : local.toLocaleDateString(undefined, { weekday: 'short' }),
      name: isToday ? 'Today' : local.toLocaleDateString(undefined, { weekday: 'long' }),
      points: day.points ?? 0,
      answers: day.answers,
    }
  })
  const total = bars.reduce((sum, bar) => sum + bar.points, 0)
  const best = bars.reduce<DayBar | null>(
    (top, bar) => (top === null || bar.points > top.points ? bar : top),
    null,
  )

  return (
    <div className="card week-chart">
      <div className="week-chart__head">
        <h3>Score this week</h3>
        <p className="muted">
          {signed(total)} points
          {best && best.points > 0 && ` · best: ${best.name} ${signed(best.points)}`}
        </p>
      </div>
      <figure role="img" aria-label="Points earned on each of the last seven days">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={bars} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              interval={0}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
            />
            <YAxis
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              width={36}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
            />
            <ReferenceLine y={0} stroke="var(--border)" />
            <Tooltip
              content={DayTooltip}
              cursor={{ fill: 'var(--accent-soft)', opacity: 0.5 }}
              isAnimationActive={false}
            />
            <Bar
              dataKey="points"
              radius={[4, 4, 0, 0]}
              maxBarSize={36}
              isAnimationActive={false}
              shape={(props) => {
                const bar = props.payload as DayBar
                return (
                  <Rectangle
                    {...props}
                    fill={bar.points < 0 ? 'var(--bad)' : 'var(--accent)'}
                    fillOpacity={bar.label === 'Today' ? 1 : 0.75}
                  />
                )
              }}
            >
              {/* Only today's value is written on the chart; the rest are a tap away. */}
              <LabelList
                dataKey="points"
                position="top"
                content={({ x, y, width, value, index }) =>
                  index === bars.length - 1 ? (
                    <text
                      x={Number(x) + Number(width) / 2}
                      y={Number(y) - 6}
                      textAnchor="middle"
                      fill="var(--fg)"
                      fontSize={12}
                      fontWeight={600}
                    >
                      {signed(Number(value))}
                    </text>
                  ) : null
                }
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </figure>
      <table className="sr-only">
        <caption>Points per day</caption>
        <tbody>
          {bars.map((bar) => (
            <tr key={bar.label}>
              <th scope="row">{bar.name}</th>
              <td>{signed(bar.points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
