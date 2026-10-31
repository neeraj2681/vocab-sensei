import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RestoreSummary } from '../../api/backup'
import { fail, fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const BACKUP = { version: 1, exported_at: '2026-10-30T12:00:00Z', words: [], answers: [] }
const SUMMARY: RestoreSummary = {
  words_added: 5,
  words_kept: 0,
  answers_added: 12,
  answers_skipped: 0,
  readings_added: 1,
  books_missing: [],
}

function progressPage(extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 10, streak: 0 }),
    'GET /api/quiz/history': () => json([]),
    ...extra,
  })
}

const file = (content: string) => new File([content], 'backup.json', { type: 'application/json' })

describe('backup', () => {
  it('offers the backup as a download', async () => {
    progressPage()

    renderApp('/progress')

    const link = await screen.findByRole('link', { name: 'Download a backup' })
    expect(link).toHaveAttribute('href', '/api/backup')
    expect(link).toHaveAttribute('download')
  })

  it('restores a backup file and says what came back', async () => {
    const api = progressPage({ 'POST /api/backup': () => json(SUMMARY) })
    const user = renderApp('/progress')

    await user.upload(
      await screen.findByLabelText('Restore from a backup'),
      file(JSON.stringify(BACKUP)),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Restored 5 words and 12 answers, and 1 current reads.',
    )
    expect(api.calls('POST /api/backup')).toEqual([BACKUP])
  })

  it('names books that need uploading again', async () => {
    progressPage({
      'POST /api/backup': () => json({ ...SUMMARY, readings_added: 0, books_missing: ['Emma'] }),
    })
    const user = renderApp('/progress')

    await user.upload(
      await screen.findByLabelText('Restore from a backup'),
      file(JSON.stringify(BACKUP)),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Upload Emma to restore your place in them.',
    )
  })

  it('rejects files that are not JSON', async () => {
    const api = progressPage()
    const user = renderApp('/progress')

    await user.upload(await screen.findByLabelText('Restore from a backup'), file('not json'))

    expect(await screen.findByRole('alert')).toHaveTextContent('isn’t a Vocab Sensei backup')
    expect(api.calls('POST /api/backup')).toHaveLength(0)
  })

  it('shows why the server refused a backup', async () => {
    progressPage({ 'POST /api/backup': () => fail(422, 'This backup is version 2; expected 1') })
    const user = renderApp('/progress')

    await user.upload(
      await screen.findByLabelText('Restore from a backup'),
      file(JSON.stringify(BACKUP)),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('version 2')
  })
})
