import { Link } from 'react-router'
import { readingsApi, type Reading } from '../../api/readings'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'
import { chapterLabel } from './labels'

interface Props {
  readings: Reading[]
  onChange: () => void
}

/** The books being read, in the order quizzes draw from them. */
export function CurrentReadings({ readings, onChange }: Props) {
  const { busy, error, run } = useSubmit()

  function act(action: () => Promise<unknown>) {
    void run(async () => {
      await action()
      onChange()
    })
  }

  function move(from: number, to: number) {
    const ids = readings.map((r) => r.document.id)
    ids.splice(to, 0, ...ids.splice(from, 1))
    act(() => readingsApi.reorder(ids))
  }

  return (
    <section aria-labelledby="reading-heading" className="panel">
      <h3 id="reading-heading">Currently reading</h3>
      {readings.length === 0 ? (
        <p className="muted">
          Nothing yet. Choose “Start reading” on a book below; its words go into your quizzes.
        </p>
      ) : (
        <ol className="readings">
          {readings.map((reading, i) => {
            const { id, title } = reading.document
            return (
              <li key={id} className="row">
                <span>
                  <Link to={`/books/${String(id)}`}>{title}</Link>
                  <span className="muted">
                    {' · '}
                    {chapterLabel(reading.current_chapter_index, reading.current_chapter_title)}
                  </span>
                </span>
                <span className="row__actions">
                  <button
                    type="button"
                    aria-label={`Move ${title} up`}
                    disabled={busy || i === 0}
                    onClick={() => {
                      move(i, i - 1)
                    }}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${title} down`}
                    disabled={busy || i === readings.length - 1}
                    onClick={() => {
                      move(i, i + 1)
                    }}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      act(() => readingsApi.stop(id))
                    }}
                  >
                    Stop reading
                  </button>
                </span>
              </li>
            )
          })}
        </ol>
      )}
      <FormError message={error} />
    </section>
  )
}
