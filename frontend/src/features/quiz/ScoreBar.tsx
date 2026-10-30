import type { QuizStats } from '../../api/quiz'
import { Sparkline } from './Sparkline'

export interface Pop {
  id: number // a new id restarts the animation
  delta: number
  correct: boolean
}

interface Props {
  stats: QuizStats
  pop: Pop | null
  recent: number[] // lifetime totals after each answer this visit, oldest first
}

const formatDelta = (delta: number) =>
  delta > 0 ? `+${String(delta)}` : delta < 0 ? `−${String(-delta)}` : '0'

/** Live lifetime score with a +5 / −10 pop, recent trend and today's progress. */
export function ScoreBar({ stats, pop, recent }: Props) {
  const goalMet = stats.today >= stats.daily_goal

  return (
    <div className="scorebar">
      <div className="scorebar__score">
        <span className="scorebar__label">Score</span>
        <span
          key={pop?.id}
          className={`scorebar__total ${pop ? `scorebar__total--${pop.correct ? 'up' : 'down'}` : ''}`}
          data-testid="score"
        >
          {stats.total.toLocaleString()}
        </span>
        {pop && (
          <span
            key={`pop-${String(pop.id)}`}
            className={`pop pop--${pop.correct ? 'up' : 'down'}`}
            aria-hidden="true"
          >
            {formatDelta(pop.delta)}
          </span>
        )}
      </div>
      <Sparkline values={recent} />
      <div className="scorebar__daily">
        <span title="Days in a row with your daily goal met">🔥 {stats.streak}-day streak</span>
        <span className={goalMet ? 'scorebar__goal scorebar__goal--met' : 'scorebar__goal'}>
          Today {stats.today}/{stats.daily_goal}
          {goalMet && ' ✓'}
        </span>
      </div>
    </div>
  )
}
