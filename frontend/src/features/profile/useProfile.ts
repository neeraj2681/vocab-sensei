import { useEffect, useState } from 'react'
import { leaderboardApi, type Profile } from '../../api/leaderboard'

/** Loads a profile; `error` says it couldn't (a hidden profile reads as not found). */
export function useProfile(userId: number | undefined) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (userId === undefined) return
    let current = true
    leaderboardApi
      .profile(userId)
      .then((loaded) => {
        if (current) setProfile(loaded)
      })
      .catch(() => {
        if (current) setError('Couldn’t load this profile.')
      })
    return () => {
      current = false
    }
  }, [userId])

  return { profile, error }
}
