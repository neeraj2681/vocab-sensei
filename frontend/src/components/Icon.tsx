// Fluent Emoji 3D by Microsoft (MIT licence; see public/icons/LICENSE-fluent-emoji.txt).
export type IconName =
  | 'amphora'
  | 'camel'
  | 'camera'
  | 'coin'
  | 'crescent_moon'
  | 'diya_lamp'
  | 'door'
  | 'gear'
  | 'hourglass'
  | 'man'
  | 'palm_tree'
  | 'person'
  | 'pot'
  | 'shopping_bags'
  | 'woman'
  | 'bar_chart'
  | 'books'
  | 'bust_in_silhouette'
  | 'check_mark_button'
  | 'cross_mark'
  | 'direct_hit'
  | 'fire'
  | 'house'
  | 'input_latin_letters'
  | 'locked'
  | 'open_book'
  | 'party_popper'
  | 'seedling'
  | 'sparkles'
  | 'speaker_high_volume'
  | 'star'
  | 'trophy'

/** A decorative 3D icon; the text next to it (or the button's label) carries the meaning. */
export function Icon({ name, size = 24 }: { name: IconName; size?: number }) {
  return (
    <img
      className="icon"
      src={`/icons/${name}.png`}
      alt=""
      width={size}
      height={size}
      draggable={false}
    />
  )
}
