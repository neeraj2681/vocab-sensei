import type { User } from '../api/auth'
import { Icon, type IconName } from './Icon'

const FIGURE: Record<NonNullable<User['gender']>, IconName> = {
  male: 'man',
  female: 'woman',
  unspecified: 'person',
}

type Person = Pick<User, 'gender' | 'has_avatar' | 'avatar_stamp'>

/** The user in a circle: their uploaded photo, or a figure that matches the gender they picked.
`src` is someone else's photo (from their profile); without it, it's your own. */
export function Avatar({
  user,
  size = 28,
  src,
}: {
  user: Person | null
  size?: number
  src?: string
}) {
  const style = { width: size, height: size }
  if (user?.has_avatar) {
    return (
      <img
        className="avatar"
        src={src ?? `/api/auth/me/avatar?v=${String(user.avatar_stamp ?? 0)}`}
        alt=""
        style={style}
        draggable={false}
      />
    )
  }
  return (
    <span className="avatar avatar--figure" style={style}>
      <Icon name={FIGURE[user?.gender ?? 'unspecified']} size={Math.round(size * 0.72)} />
    </span>
  )
}
