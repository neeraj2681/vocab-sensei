import { useState } from 'react'
import { documentsApi, type BookDocument } from '../../api/documents'

/** The book's own cover thumbnail, or a drawn one (title and author on a colour from its id). */
export function BookCover({ book }: { book: BookDocument }) {
  const [failed, setFailed] = useState(false)

  if (book.has_cover && !failed) {
    return (
      <img
        className="cover"
        src={documentsApi.coverUrl(book.id)}
        alt=""
        loading="lazy"
        onError={() => {
          setFailed(true)
        }}
      />
    )
  }
  const hue = (book.id * 47) % 360 // stable per book, spread around the colour wheel
  return (
    <span
      className="cover cover--drawn"
      style={{ '--cover-hue': String(hue) } as React.CSSProperties}
      aria-hidden="true"
    >
      <span className="cover__title">{book.title}</span>
      {book.author && <span className="cover__author">{book.author}</span>}
    </span>
  )
}
