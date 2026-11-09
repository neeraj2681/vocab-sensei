import { useEffect, useRef, useState } from 'react'
import { authApi } from '../api/auth'
import { useAuth } from '../features/auth/AuthContext'
import { Avatar } from './Avatar'
import { FormError } from './Form'
import { Icon } from './Icon'
import { useSubmit } from './useSubmit'

/** Your own photo, with a camera band across its lower part: tap it for Change photo, Remove
photo or Cancel. */
export function PhotoEditor({ size }: { size: number }) {
  const { user, updateUser } = useAuth()
  const { busy, error, run } = useSubmit()
  const [menu, setMenu] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  if (!user) return null
  const hasPhoto = Boolean(user.has_avatar)

  function upload(file: File | undefined) {
    if (!file) return
    void run(async () => {
      const saved = await authApi.setAvatar(file)
      updateUser({ ...saved, avatar_stamp: Date.now() })
    })
  }

  return (
    <div className="photo-editor">
      <div className="photo-editor__photo" style={{ width: size, height: size }}>
        <Avatar user={user} size={size} />
        <span className="photo-editor__clip">
          <button
            type="button"
            className="photo-editor__band"
            aria-label={hasPhoto ? 'Change or remove your photo' : 'Add a photo'}
            aria-haspopup="dialog"
            disabled={busy}
            onClick={() => {
              setMenu(true)
            }}
          >
            <Icon name="camera" size={Math.round(size * 0.22)} />
          </button>
        </span>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        aria-label="Profile photo"
        hidden
        onChange={(event) => {
          upload(event.target.files?.[0])
          event.target.value = ''
        }}
      />
      <FormError message={error} />
      {menu && (
        <PhotoMenu
          hasPhoto={hasPhoto}
          onClose={() => {
            setMenu(false)
          }}
          onChange={() => {
            setMenu(false)
            fileInput.current?.click() // still inside the tap, so the browser allows it
          }}
          onRemove={() => {
            setMenu(false)
            void run(async () => {
              await authApi.removeAvatar()
              updateUser({ has_avatar: false })
            })
          }}
        />
      )}
    </div>
  )
}

function PhotoMenu({
  hasPhoto,
  onClose,
  onChange,
  onRemove,
}: {
  hasPhoto: boolean
  onClose: () => void
  onChange: () => void
  onRemove: () => void
}) {
  const first = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    first.current?.focus()
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
        className="word-card photo-menu"
        role="dialog"
        aria-modal="true"
        aria-labelledby="photo-menu-title"
      >
        <h3 id="photo-menu-title">Profile photo</h3>
        <button ref={first} type="button" className="primary" onClick={onChange}>
          {hasPhoto ? 'Change photo' : 'Upload a photo'}
        </button>
        {hasPhoto && (
          <button type="button" className="photo-menu__remove" onClick={onRemove}>
            Remove photo
          </button>
        )}
        <button type="button" className="link-button" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  )
}
