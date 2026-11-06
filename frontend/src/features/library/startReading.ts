import { ApiError } from '../../api/client'
import { readingsApi, type Reading } from '../../api/readings'

export const MAX_READING = 2 // the server's limit on books read at once

/** Starts `documentId`, or calls `onFull` (without asking the server) while two books are being
read. The server's refusal, if the list was out of date, ends the same way. Returns whether the
book was started. */
export async function startReading(
  documentId: number,
  readings: Reading[],
  onFull: () => void,
): Promise<boolean> {
  if (readings.length >= MAX_READING) {
    onFull()
    return false
  }
  try {
    await readingsApi.start(documentId)
    return true
  } catch (err) {
    if (err instanceof ApiError && err.status === 409 && err.message.includes('reading 2 books')) {
      onFull()
      return false
    }
    throw err
  }
}
