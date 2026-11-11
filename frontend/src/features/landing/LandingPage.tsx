import { useState } from 'react'
import { Link } from 'react-router'
import { usePageTitle } from '../../components/usePageTitle'
import { AppIntro } from '../auth/AppIntro'
import { BookCover } from '../library/BookCover'

const OPTIONS = [
  'bad temper; anger',
  'an organ near the stomach',
  'a feeling of great joy',
  'a sudden fear',
]
const CORRECT = 0
const EXPLAIN =
  'In old books “spleen” often means bad temper. Vocab Sensei teaches the meaning each book uses.'

// The built-in classics. Their word lists are server-rendered pages, so these are plain links.
const CLASSICS = [
  ['Alice’s Adventures in Wonderland', 'alices-adventures-in-wonderland'],
  ['The Adventures of Sherlock Holmes', 'the-adventures-of-sherlock-holmes'],
  ['Pride and Prejudice', 'pride-and-prejudice'],
  ['Frankenstein', 'frankenstein-or-the-modern-prometheus'],
  ['The Picture of Dorian Gray', 'the-picture-of-dorian-gray'],
  ['Dracula', 'dracula'],
  ['Jane Eyre', 'jane-eyre-an-autobiography'],
  ['Moby-Dick', 'moby-dick-or-the-whale'],
] as const

/** One question to tap, built from the quiz's own styles; nothing is sent anywhere. */
function SampleQuestion() {
  const [chosen, setChosen] = useState<number | null>(null)

  function optionClass(index: number) {
    if (chosen === null) return 'option'
    if (index === CORRECT) return 'option option--correct'
    if (index === chosen) return 'option option--wrong'
    return 'option option--dim'
  }

  return (
    <div className="quiz__card">
      <blockquote className="quiz__sentence">
        it is a way I have of driving off the <mark>spleen</mark>
      </blockquote>
      <p className="muted quiz__prompt">What does “spleen” mean here?</p>
      <ol className="options">
        {OPTIONS.map((option, index) => (
          <li key={option}>
            <button
              type="button"
              className={optionClass(index)}
              disabled={chosen !== null}
              onClick={() => {
                setChosen(index)
              }}
            >
              <span className="option__key" aria-hidden="true">
                {index + 1}
              </span>
              {option}
            </button>
          </li>
        ))}
      </ol>
      {chosen !== null && (
        <p role="status" className="landing__result">
          {chosen === CORRECT ? 'Right! ' : 'Not quite: here “spleen” means bad temper. '}
          {EXPLAIN}
        </p>
      )}
      {chosen !== null && (
        <p>
          <Link to="/register">Try another way to learn: create an account</Link>
        </p>
      )}
    </div>
  )
}

/** What visitors who aren't logged in see at "/". */
export function LandingPage() {
  usePageTitle(null)
  return (
    <div className="landing">
      <section className="landing__hero">
        <h1>Learn the hard words of the books you read</h1>
        <p>
          Upload a book or pick a classic: Vocab Sensei finds its hard words chapter by chapter and
          teaches them in a quick daily quiz, before you meet them in the story.
        </p>
        <p className="landing__actions">
          <Link className="primary" to="/register">
            Create a free account
          </Link>
          <Link className="secondary" to="/login">
            Log in
          </Link>
        </p>
      </section>

      <section aria-labelledby="landing-try">
        <h2 id="landing-try">Try one</h2>
        <SampleQuestion />
      </section>

      <AppIntro />

      <section aria-labelledby="landing-classics">
        <h2 id="landing-classics">Start with a classic</h2>
        <p className="muted">The hardest words of every chapter, free to browse.</p>
        <ul className="landing__classics">
          {CLASSICS.map(([title, slug], index) => (
            <li key={slug}>
              <a href={`/classics/${slug}`}>
                <BookCover book={{ id: index + 1, title, author: null, has_cover: false }} />
                <span className="landing__classic-title">{title}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>

      <footer className="landing__footer">
        <Link to="/terms">Terms</Link>
        <Link to="/privacy">Privacy</Link>
        <Link to="/copyright">Copyright</Link>
        <a href="/classics">Browse all books</a>
      </footer>
    </div>
  )
}
