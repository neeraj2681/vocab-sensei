import { apiGet, apiPost } from './client'
import { timeZone } from './quiz'

export type QuestKind = 'answer' | 'right' | 'in_a_row' | 'ninja' | 'learn' | 'book' | 'early'

export interface Quest {
  key: string
  kind: QuestKind
  tier: 'easy' | 'medium' | 'hard'
  title: string
  target: number
  progress: number
  reward: number // coins
  claimed: boolean
}

export interface DailyQuests {
  quests: Quest[]
  chest_reward: number // for claiming all three
  chest_ready: boolean
  chest_claimed: boolean
}

export interface ClaimResult {
  coins: number
  total: number // lifetime coins now
  quests: DailyQuests
}

const tz = () => `tz=${encodeURIComponent(timeZone())}`

export const questsApi = {
  today: () => apiGet<DailyQuests>(`/quests?${tz()}`),
  claim: (key: string) => apiPost<ClaimResult>(`/quests/${encodeURIComponent(key)}/claim?${tz()}`),
}
