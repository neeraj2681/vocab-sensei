import type { QuizStats } from '../../api/quiz'
import { Icon } from '../../components/Icon'
import { formatCountdown, useCountdown } from '../../components/useCountdown'
import { NINJA, SESSION_LENGTH, ninja, type Combo } from './combo'

export interface Pop {
  id: number // a new id restarts the animation
  delta: number
  correct: boolean
}

const formatDelta = (delta: number) =>
  delta > 0 ? `+${String(delta)}` : delta < 0 ? `−${String(-delta)}` : '0'

interface Props {
  answered: number // answers given in this session
  combo: Combo
  stats: QuizStats | null
  pop: Pop | null
  onLeave: () => void
}

/** One row: ✕ to leave, how far into the session you are, your run of right answers, your coins. */
export function QuizHeader({ answered, combo, stats, pop, onLeave }: Props) {
  const done = Math.min(answered, SESSION_LENGTH)
  const doubleLeft = useCountdown(stats?.double_coins_until)

  return (
    <div className="quiz-header">
      <button
        type="button"
        className="session-bar__quit"
        aria-label="End session"
        onClick={onLeave}
      >
        ✕
      </button>
      <div
        className="session-bar__progress"
        role="progressbar"
        aria-label="Session progress"
        aria-valuemin={0}
        aria-valuemax={SESSION_LENGTH}
        aria-valuenow={done}
      >
        <span style={{ width: `${String((done / SESSION_LENGTH) * 100)}%` }} />
      </div>
      {ninja(combo) ? (
        <span
          className="stat-pill stat-pill--ninja"
          title={`${String(combo.run)} right in a row: double coins until a miss`}
        >
          <Icon name="ninja" size={22} /> ×{combo.multiplier}
          <span className="sr-only">
            {' '}
            {NINJA}, {combo.run} in a row
          </span>
        </span>
      ) : (
        <span
          className="stat-pill ninja-meter"
          role="meter"
          aria-label={`Right answers in a row towards ${NINJA}`}
          aria-valuemin={0}
          aria-valuemax={combo.after}
          aria-valuenow={combo.run}
          title={`${String(combo.after)} right in a row start ${NINJA} (double coins)`}
        >
          <Icon name="ninja" size={20} />
          <span className="ninja-meter__segments" aria-hidden="true">
            {Array.from({ length: combo.after }, (_, i) => (
              <span key={i} className={i < combo.run ? 'ninja-meter__on' : undefined} />
            ))}
          </span>
          <span className="sr-only">
            {combo.run} of {combo.after} right in a row
          </span>
        </span>
      )}
      {stats && (
        <div className="scorebar__score">
          <span className="scorebar__label">
            <Icon name="coin" size={20} /> <span className="sr-only">Coins</span>
          </span>
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
          {doubleLeft !== null && doubleLeft > 0 && (
            <span className="scorebar__double" title="Double coins from the Shop">
              <Icon name="double_coins" size={20} /> 2× · {formatCountdown(doubleLeft)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

/** "Today 12/20 · 4-day streak", in the goal-met colour once today's goal is reached. */
export function DailyLine({ stats }: { stats: QuizStats }) {
  const goalMet = stats.today >= stats.daily_goal
  return (
    <p className="daily-line">
      <span className={goalMet ? 'scorebar__goal scorebar__goal--met' : 'scorebar__goal'}>
        Today {stats.today}/{stats.daily_goal}
        {goalMet && ' ✓'}
      </span>
      {stats.streak > 0 && (
        <>
          <span aria-hidden="true">·</span>
          <span title="Days in a row with your daily goal met">
            <Icon name="fire" size={18} /> {stats.streak}-day streak
          </span>
        </>
      )}
    </p>
  )
}
