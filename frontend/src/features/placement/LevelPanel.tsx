import { Link } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { levelName } from './levels'

/** Settings: the reader's word level, and the check to set or redo it. */
export function LevelPanel() {
  const { user } = useAuth()
  const level = user?.vocab_level ?? null
  return (
    <section aria-labelledby="level-heading" className="panel">
      <h3 id="level-heading">Your word level</h3>
      <p>
        {level === null ? (
          'Not measured yet: every word in your books comes into your quizzes.'
        ) : (
          <>
            <strong>{levelName(level)}</strong>. Words much easier than this are kept aside as
            “Probably known” (see Words).
          </>
        )}
      </p>
      <Link to="/placement">
        {level === null ? 'Take the 2-minute check' : 'Take the check again'}
      </Link>
    </section>
  )
}
