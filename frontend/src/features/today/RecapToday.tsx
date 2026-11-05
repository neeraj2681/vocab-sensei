import { useEffect, useState } from 'react'
import { recapsApi, type Recap } from '../../api/recaps'
import { RecapCard } from '../recaps/RecapCard'

/** On Mondays, last week's recap on the home screen; on the 1st, last month's. */
export function RecapToday() {
  const [recaps, setRecaps] = useState<Recap[]>([])
  const [today] = useState(() => new Date())
  const due = today.getDay() === 1 || today.getDate() === 1

  useEffect(() => {
    if (!due) return
    let current = true
    recapsApi
      .get()
      .then((loaded) => {
        const shown = []
        const lastWeek = loaded.weeks.find((r) => !r.current)
        const lastMonth = loaded.months.find((r) => !r.current)
        if (today.getDay() === 1 && lastWeek) shown.push(lastWeek)
        if (today.getDate() === 1 && lastMonth) shown.push(lastMonth)
        if (current) setRecaps(shown)
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [due, today])

  return (
    <>
      {recaps.map((recap) => (
        <RecapCard
          key={recap.period}
          recap={recap}
          title={recap.period === 'week' ? 'Your week' : 'Your month'}
        />
      ))}
    </>
  )
}
