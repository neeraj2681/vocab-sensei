import type { User } from '../api/auth'
import { Icon, type IconName } from './Icon'

const FIGURE: Record<NonNullable<User['gender']>, IconName> = {
  male: 'man',
  female: 'woman',
  unspecified: 'person',
}

/** The user in a circle: their uploaded photo, or a figure that matches the gender they picked. */
export function Avatar({ user, size = 28 }: { user: User | null; size?: number }) {
  const style = { width: size, height: size }
  if (user?.has_avatar) {
    return (
      <img
        className="avatar"
        src={`/api/auth/me/avatar?v=${String(user.avatar_stamp ?? 0)}`}
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
