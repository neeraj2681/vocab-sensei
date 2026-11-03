import { useEffect, useState } from 'react'
import { questsApi, type DailyQuests, type Quest, type QuestKind } from '../../api/quests'
import { Burst } from '../../components/Burst'
import { FormError } from '../../components/Form'
import { Icon, type IconName } from '../../components/Icon'
import { sounds } from '../../components/sounds'
import { useSubmit } from '../../components/useSubmit'

const KIND_ICON: Record<QuestKind, IconName> = {
  answer: 'direct_hit',
  right: 'check_mark_button',
  in_a_row: 'sparkles',
  ninja: 'ninja',
  learn: 'seedling',
  book: 'open_book',
  early: 'sunrise',
}

/** Today's three quests on the home screen: progress, and a Claim button once one is done. */
export function QuestsPanel({ onClaimed }: { onClaimed: (total: number) => void }) {
  const [daily, setDaily] = useState<DailyQuests | null>(null)
  const [popped, setPopped] = useState<{ key: string; coins: number } | null>(null)
  const { busy, error, run } = useSubmit()

  useEffect(() => {
    let current = true
    questsApi
      .today()
      .then((loaded) => {
        if (current) setDaily(loaded)
      })
      .catch(() => undefined) // the rest of Today still works
    return () => {
      current = false
    }
  }, [])

  if (!daily) return null

  function claim(key: string) {
    void run(async () => {
      const result = await questsApi.claim(key)
      if (key === 'chest') sounds.chest()
      else sounds.coin()
      setDaily(result.quests)
      setPopped({ key, coins: result.coins })
      onClaimed(result.total)
    })
  }

  const allClaimed = daily.quests.every((q) => q.claimed)
  return (
    <section className="card quests" aria-labelledby="quests-heading">
      <div className="quests__head">
        <h3 id="quests-heading">Daily quests</h3>
        <span className="muted">New ones at midnight</span>
      </div>
      <ul className="quests__list">
        {daily.quests.map((quest) => (
          <QuestRow
            key={quest.key}
            quest={quest}
            busy={busy}
            popped={popped?.key === quest.key ? popped.coins : null}
            onClaim={() => {
              claim(quest.key)
            }}
          />
        ))}
        <li className={`quest quest--chest${daily.chest_ready ? ' quest--done' : ''}`}>
          {popped?.key === 'chest' && <Burst />}
          <Icon name="wrapped_gift" size={36} />
          <span className="quest__text">
            <strong>{daily.chest_claimed ? 'Chest opened' : 'Bonus chest'}</strong>
            <span className="muted">
              {daily.chest_claimed
                ? 'All of today’s quests done. See you tomorrow!'
                : allClaimed
                  ? 'All three claimed: open it!'
                  : 'Claim all three quests to open it'}
            </span>
          </span>
          <Reward
            reward={daily.chest_reward}
            done={daily.chest_ready}
            claimed={daily.chest_claimed}
            label="Open"
            busy={busy}
            popped={popped?.key === 'chest' ? popped.coins : null}
            onClaim={() => {
              claim('chest')
            }}
          />
        </li>
      </ul>
      <FormError message={error} />
    </section>
  )
}

function QuestRow({
  quest,
  busy,
  popped,
  onClaim,
}: {
  quest: Quest
  busy: boolean
  popped: number | null
  onClaim: () => void
}) {
  const done = quest.progress >= quest.target
  return (
    <li className={`quest${done && !quest.claimed ? ' quest--done' : ''}`}>
      <Icon name={KIND_ICON[quest.kind]} size={36} />
      <span className="quest__text">
        <strong>{quest.title}</strong>
        <span className="quest__progress">
          <span className="bar" aria-hidden="true">
            <span style={{ width: `${String((quest.progress / quest.target) * 100)}%` }} />
          </span>
          <span className="muted">
            {quest.progress}/{quest.target}
          </span>
        </span>
      </span>
      <Reward
        reward={quest.reward}
        done={done}
        claimed={quest.claimed}
        label="Claim"
        busy={busy}
        popped={popped}
        onClaim={onClaim}
      />
    </li>
  )
}

/** The coins on offer: muted until done, then a Claim button, then a tick. */
function Reward({
  reward,
  done,
  claimed,
  label,
  busy,
  popped,
  onClaim,
}: {
  reward: number
  done: boolean
  claimed: boolean
  label: string
  busy: boolean
  popped: number | null
  onClaim: () => void
}) {
  if (claimed) {
    return (
      <span className="quest__reward quest__reward--claimed">
        {popped !== null && (
          <span className="pop pop--up" aria-hidden="true">
            +{popped}
          </span>
        )}
        <Icon name="check_mark_button" size={22} />
        <span className="sr-only">Claimed</span>
      </span>
    )
  }
  if (done) {
    return (
      <button type="button" className="quest__claim" disabled={busy} onClick={onClaim}>
        {label} <Icon name="coin" size={18} /> +{reward}
      </button>
    )
  }
  return (
    <span className="quest__reward muted">
      <Icon name="coin" size={18} /> +{reward}
    </span>
  )
}
