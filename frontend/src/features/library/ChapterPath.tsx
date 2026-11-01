import { useState } from 'react'
import type { ChapterReadiness } from '../../api/documents'
import { Icon, type IconName } from '../../components/Icon'
import { chapterLabel } from './labels'

const RADIUS = 33
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const BEFORE = 2 // chapters shown before the current one until "Show all"
const AFTER = 7

interface Props {
  chapters: ChapterReadiness[]
  current: number | null // the chapter being read, if this is a current read
  selected: number
  onSelect: (index: number) => void
}

/** The book as a path of chapters, each ring filled by how ready you are for it. */
export function ChapterPath({ chapters, current, selected, onSelect }: Props) {
  const [all, setAll] = useState(false)
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
              onClick={() => {
                onSelect(chapter.index)
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

function nodeIcon(chapter: ChapterReadiness, current: number | null): IconName {
  if (chapter.readiness >= 100) return 'star'
  if (chapter.index === current) return 'open_book'
  return chapter.readiness > 0 ? 'direct_hit' : 'seedling'
}
