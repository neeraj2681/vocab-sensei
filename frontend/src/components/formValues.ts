interface SubmitLike {
  preventDefault: () => void
  currentTarget: HTMLFormElement
}

/** Stops the browser's own submit and returns the form's named text fields. */
export function formValues(event: SubmitLike): Record<string, string> {
  event.preventDefault()
  const values: Record<string, string> = {}
  for (const [key, value] of new FormData(event.currentTarget)) {
    if (typeof value === 'string') values[key] = value
  }
  return values
}
