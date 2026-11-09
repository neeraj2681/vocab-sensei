/** The same names the server gives levels (app/quiz/placement.py). */
export function levelName(level: number) {
  if (level <= 2.25) return 'Expert'
  if (level <= 3.0) return 'Advanced'
  if (level <= 3.75) return 'Confident'
  if (level <= 4.5) return 'Growing'
  return 'Getting started'
}
