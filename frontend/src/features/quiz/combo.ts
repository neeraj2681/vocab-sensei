export const SESSION_LENGTH = 10 // answers in a session, then a summary
export const NINJA = 'Ninja Mode' // the combo: right answers in a row multiply the coins

/** The run of right answers and when it turns into Ninja Mode (the server's rules). */
export interface Combo {
  run: number // right answers in a row, kept between sessions
  after: number // Ninja Mode from this many in a row...
  multiplier: number // ...multiplying right answers' coins by this
}

export const ninja = (combo: Combo) => combo.run >= combo.after
