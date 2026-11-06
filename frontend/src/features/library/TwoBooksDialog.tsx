import { useEffect, useRef } from 'react'
import { Icon } from '../../components/Icon'

/** Shown on "Start reading" while two books are already being read: one has to go first. */
export function TwoBooksDialog({
  onClose,
  onRemove,
}: {
  onClose: () => void
  onRemove: () => void
}) {
  const remove = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    remove.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return (
    <div
      className="word-card__backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="word-card two-books"
        role="dialog"
        aria-modal="true"
        aria-labelledby="two-books-title"
      >
        <Icon name="open_book" size={48} />
        <h3 id="two-books-title">You're reading 2 books</h3>
        <p>Stop reading one of them first: its progress is kept.</p>
        <button ref={remove} type="button" className="primary" onClick={onRemove}>
          Remove a book from current reads
        </button>
      </div>
    </div>
  )
}
