import type { Recap } from '../../api/recaps'
import { Icon } from '../../components/Icon'
import { day, recapSpan, recapTitle } from './span'

/** A finished week or month at a glance: the numbers, then its highlights. */
export function RecapCard({ recap, title }: { recap: Recap; title?: string }) {
  const accuracy = recap.answers
    ? `${String(Math.round((100 * recap.right) / recap.answers))}%`
    : '—'
  return (
    <section className="card recap" aria-label={title ?? `Recap ${recapSpan(recap)}`}>
      <div className="recap__head">
        <Icon name="party_popper" size={36} />
        <div>
          <h3>{title ?? recapTitle(recap)}</h3>
          <p className="muted">
            {recapSpan(recap)}
            {recap.current && ' · so far'}
          </p>
        </div>
      </div>
      {recap.answers === 0 ? (
        <p className="muted">No answers this {recap.period}. A fresh start awaits!</p>
      ) : (
        <>
          <dl className="recap__numbers">
            <div>
              <dt>Words learned</dt>
              <dd>{recap.words_learned.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Coins earned</dt>
              <dd>
                <Icon name="coin" size={20} /> {recap.coins.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt>Answers</dt>
              <dd>
                {recap.answers.toLocaleString()} · {accuracy}
              </dd>
            </div>
            <div>
              <dt>Goal met</dt>
              <dd>
                {recap.days > 0
                  ? `${String(recap.goal_days)}/${String(recap.days)} days`
                  : 'Not yet'}
              </dd>
            </div>
          </dl>
          <ul className="recap__highlights">
            {recap.best_day && (
              <li>
                <Icon name="star" size={22} /> Best day:{' '}
                <strong>
                  {day(recap.best_day, { weekday: 'long', day: 'numeric', month: 'short' })}
                </strong>{' '}
                (+{recap.best_day_coins.toLocaleString()})
              </li>
            )}
            {recap.toughest_word && (
              <li>
                <Icon name="direct_hit" size={22} /> Toughest word:{' '}
                <strong>{recap.toughest_word}</strong>
              </li>
            )}
            {recap.favourite_book && (
              <li>
                <Icon name="open_book" size={22} /> Favourite book:{' '}
                <strong>{recap.favourite_book}</strong>
              </li>
            )}
            <li>
              <Icon name="fire" size={22} />{' '}
              {recap.current ? 'Day streak now' : `Day streak at the end of the ${recap.period}`}:{' '}
              <strong>{recap.streak}</strong>
            </li>
          </ul>
        </>
      )}
    </section>
  )
}
