import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import type { ChapterReadiness } from '../../api/documents'
import { Icon, type IconName } from '../../components/Icon'
import { chapterLabel } from './labels'

const RADIUS = 33
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const BEFORE = 2 // chapters shown before the current one until "Show all"
const AFTER = 7

interface Props {
  documentId: number
  chapters: ChapterReadiness[]
  current: number | null // the chapter being read, if this is a current read
  selected: number
  onSelect: (index: number) => void
}

/** The book as a path of chapters, each ring filled by how ready you are for it. */
export function ChapterPath({ documentId, chapters, current, selected, onSelect }: Props) {
  const [all, setAll] = useState(false)
  const [open, setOpen] = useState<number | null>(null) // the chapter whose bubble is showing

  // A tap anywhere else on the page (or Esc) closes the bubble; chapters handle their own taps.
  useEffect(() => {
    if (open === null) return
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Element | null
      if (!target?.closest('.practice-bubble, .path__node')) setOpen(null)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(null)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  const anchor = current ?? selected
  const from = all ? 0 : Math.max(0, anchor - BEFORE)
  const to = all ? chapters.length : Math.min(chapters.length, anchor + AFTER + 1)
  const shown = chapters.slice(from, to)

  return (
    <div className="path">
      {from > 0 && <p className="muted path__more">{from} earlier chapters</p>}
      <ol className="path__nodes">
        {shown.map((chapter) => (
          <li key={chapter.index}>
            <button
              type="button"
              className={[
                'path__node',
                chapter.index === current ? 'path__node--current' : '',
                chapter.index === selected ? 'path__node--selected' : '',
              ].join(' ')}
              aria-pressed={chapter.index === selected}
              aria-label={`Chapter ${String(chapter.index + 1)}, ${chapterLabel(chapter.index, chapter.title)}, ${String(chapter.readiness)}% ready`}
              aria-expanded={open === chapter.index}
              onClick={() => {
                onSelect(chapter.index)
                setOpen((shown) => (shown === chapter.index ? null : chapter.index)) // tap again: close
              }}
            >
              <span className="path__disc">
                <svg viewBox="0 0 76 76" aria-hidden="true">
                  <circle className="path__track" cx="38" cy="38" r={RADIUS} />
                  <circle
                    className="path__done"
                    cx="38"
                    cy="38"
                    r={RADIUS}
                    strokeDasharray={CIRCUMFERENCE}
                    strokeDashoffset={CIRCUMFERENCE * (1 - chapter.readiness / 100)}
                  />
                </svg>
                <span className="path__face">
                  <Icon name={nodeIcon(chapter, current)} size={34} />
                </span>
              </span>
              <span className="path__caption" aria-hidden="true">
                {chapter.index + 1}. {chapterLabel(chapter.index, chapter.title)}
                <br />
                {chapter.readiness}%
              </span>
            </button>
            {open === chapter.index && <PracticeBubble documentId={documentId} chapter={chapter} />}
          </li>
        ))}
      </ol>
      {(from > 0 || to < chapters.length) && (
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setAll(true)
          }}
        >
          Show all {chapters.length} chapters
        </button>
      )}
    </div>
  )
}

/** Under a tapped chapter: what it holds and a 3D Practice button for a quiz on its words only. */
function PracticeBubble({
  documentId,
  chapter,
}: {
  documentId: number
  chapter: ChapterReadiness
}) {
  const ready = chapter.readiness >= 100
  const bubble = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Bring all of it into view (above the phone's tab bar; see scroll-margin in index.css).
    const node = bubble.current
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [])

  return (
    <div
      ref={bubble}
      className="practice-bubble"
      role="group"
      aria-label={`Chapter ${String(chapter.index + 1)}`}
    >
      <strong>
        {chapter.index + 1}. {chapterLabel(chapter.index, chapter.title)}
      </strong>
      <span className="muted">
        {chapter.words.toLocaleString()} {chapter.words === 1 ? 'word' : 'words'} ·{' '}
        {chapter.readiness}% ready
      </span>
      {ready ? (
        <span className="practice-bubble__done">
          <Icon name="star" size={22} /> Every word here is ready
        </span>
      ) : (
        <Link
          className="button-link primary practice-bubble__go"
          to={`/quiz?book=${String(documentId)}&chapter=${String(chapter.index)}`}
        >
          <Icon name="direct_hit" size={22} /> Practice
        </Link>
      )}
    </div>
  )
}

function nodeIcon(chapter: ChapterReadiness, current: number | null): IconName {
  if (chapter.readiness >= 100) return 'star'
  if (chapter.index === current) return 'open_book'
  return chapter.readiness > 0 ? 'direct_hit' : 'seedling'
}
