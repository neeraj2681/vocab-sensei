import { useState } from 'react'
import { BACKUP_URL, backupApi, type RestoreSummary } from '../../api/backup'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'

/** Download your progress as a JSON file, or merge one back in. */
export function BackupPanel() {
  const { busy, error, setError, run } = useSubmit()
  const [summary, setSummary] = useState<RestoreSummary | null>(null)

  return (
    <section aria-labelledby="backup-heading" className="panel">
      <h3 id="backup-heading">Backup</h3>
      <p className="muted">
        Your word progress, answers and current reads in one file. Books aren’t included: after
        restoring, upload them again and your progress reattaches.
      </p>
      <p>
        <a href={BACKUP_URL} download>
          Download a backup
        </a>
      </p>
      <label htmlFor="restore-file">Restore from a backup</label>{' '}
      <input
        id="restore-file"
        type="file"
        accept=".json,application/json"
        disabled={busy}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = '' // picking the same file again should work
          if (!file) return
          setSummary(null)
          void run(async () => {
            let backup: unknown
            try {
              backup = JSON.parse(await file.text())
            } catch {
              setError('That file isn’t a Vocab Sensei backup.')
              return
            }
            setSummary(await backupApi.restore(backup))
          })
        }}
      />
      <FormError message={error} />
      {summary && (
        <p role="status">
          Restored {summary.words_added} words and {summary.answers_added} answers
          {summary.readings_added > 0 && `, and ${String(summary.readings_added)} current reads`}.
          {summary.words_kept + summary.answers_skipped > 0 &&
            ' Anything already in your account was kept.'}
          {summary.books_missing.length > 0 &&
            ` Upload ${summary.books_missing.join(', ')} to restore your place in them.`}
        </p>
      )}
    </section>
  )
}
