import { apiGet, apiPost } from './client'
import { timeZone } from './quiz'

export type ShopItem = 'streak_freeze' | 'double_coins' | 'name_change'

export interface Stock {
  item: ShopItem
  price: number
  owned: number // in the inventory now
  max_owned: number
}

export interface Shop {
  open: boolean // all of Sunday
  opens_at: string // this Sunday's start if open, else next Sunday's
  closes_at: string
  coins: number // to spend
  stock: Stock[]
  double_coins_until: string | null // double coins running until then
}

const tz = () => `tz=${encodeURIComponent(timeZone())}`

export const shopApi = {
  get: () => apiGet<Shop>(`/shop?${tz()}`),
  buy: (item: ShopItem) => apiPost<Shop>(`/shop/buy/${item}?${tz()}`),
  useDoubleCoins: () => apiPost<Shop>(`/shop/use/double_coins?${tz()}`),
}
