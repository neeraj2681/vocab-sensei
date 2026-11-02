import type { CSSProperties } from 'react'

// Words that drift out of the book: [word, sideways drift in px, start delay in s]
const WORDS: [string, number, number][] = [
  ['lucid', -70, 0],
  ['serene', 60, 0.8],
  ['ebullient', -20, 1.6],
  ['wistful', 85, 2.4],
  ['reverie', -95, 3.2],
  ['candour', 30, 4.0],
  ['ephemeral', -50, 4.8],
  ['solace', 70, 5.6],
]

/** The login page's welcome: a green book opens and its words float out. Decorative only. */
export function MagicBook() {
  return (
    <div className="magic-book" aria-hidden="true">
      <div className="magic-book__words">
        {WORDS.map(([word, drift, delay]) => (
          <span
            key={word}
            className="magic-book__word"
            style={
              { '--drift': `${String(drift)}px`, '--delay': `${String(delay)}s` } as CSSProperties
            }
          >
            {word}
          </span>
        ))}
      </div>
      <div className="magic-book__glow" />
      <div className="magic-book__book">
        <div className="magic-book__back" />
        <div className="magic-book__page magic-book__page--left" />
        <div className="magic-book__page magic-book__page--right" />
        <div className="magic-book__cover">
          <div className="magic-book__front">
            <span className="magic-book__title">Vocab Sensei</span>
          </div>
          <div className="magic-book__inside" />
        </div>
      </div>
    </div>
  )
}
