import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { shopApi, type Shop, type ShopItem, type Stock } from '../../api/shop'
import { Burst } from '../../components/Burst'
import { FormError } from '../../components/Form'
import { Icon, type IconName } from '../../components/Icon'
import { sounds } from '../../components/sounds'
import { formatCountdown, useCountdown } from '../../components/useCountdown'
import { useSubmit } from '../../components/useSubmit'

const ITEMS: Record<ShopItem, { name: string; icon: IconName; about: string }> = {
  streak_freeze: {
    name: 'Streak freeze',
    icon: 'torch',
    about:
      'Keeps your streak alive on a day you miss your goal. Used by itself; if you meet your goal, it stays for another day.',
  },
  name_change: {
    name: 'Username change',
    icon: 'name_badge',
    about:
      'One more change of your username, after the free one. Keep it and use it in Settings when you like.',
  },
  double_coins: {
    name: 'Double coins',
    icon: 'double_coins',
    about:
      'Doubles the coins of every right answer for 30 minutes (four times in Ninja Mode). Keep it and use it when you like.',
  },
}

/** The desert market: open all of Sunday with streak freezes and double coins; the rest of the
week a countdown. The inventory (and using double coins) is there every day. */
export function ShopPage() {
  const [shop, setShop] = useState<Shop | null>(null)
  const [error, setError] = useState(false)
  const [bought, setBought] = useState<ShopItem | null>(null)
  const { busy, error: actionError, run } = useSubmit()
  const opensIn = useCountdown(shop?.open ? shop.closes_at : shop?.opens_at)

  useEffect(() => {
    let current = true
    shopApi
      .get()
      .then((loaded) => {
        if (current) setShop(loaded)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [])

  // The countdown reached zero: the Shop just opened or closed, so ask again.
  useEffect(() => {
    if (opensIn !== 0) return
    let current = true
    void shopApi.get().then((loaded) => {
      if (current) setShop(loaded)
    })
    return () => {
      current = false
    }
  }, [opensIn])

  function buy(item: ShopItem) {
    void run(async () => {
      setShop(await shopApi.buy(item))
      setBought(item)
      sounds.coin()
    })
  }

  function useDoubleCoins() {
    void run(async () => {
      setShop(await shopApi.useDoubleCoins())
      sounds.ninjaStart()
    })
  }

  return (
    <section className="shop">
      <div className="shop__head">
        <h2>Shop</h2>
        {shop && (
          <span className="stat-pill" title="Your coins">
            <Icon name="coin" size={22} /> {shop.coins.toLocaleString()} coins
          </span>
        )}
      </div>

      <Market open={shop?.open ?? false} />

      {error && (
        <p role="alert" className="form-error">
          Couldn’t reach the Shop. Is the backend running?
        </p>
      )}
      {shop && !shop.open && (
        <div className="card shop__notice">
          <Icon name="hourglass" size={48} />
          <div>
            <h3>The merchant comes on Sunday</h3>
            <p className="muted">The Shop is open all day every Sunday. Keep earning coins!</p>
            {opensIn !== null && (
              <p className="shop__timer" role="timer" aria-label="Opens in">
                Opens in <strong>{formatCountdown(opensIn)}</strong>
              </p>
            )}
          </div>
        </div>
      )}
      {shop?.open && (
        <>
          <div className="card shop__notice shop__notice--open">
            <Icon name="shopping_bags" size={48} />
            <div>
              <h3>The merchant is here!</h3>
              {opensIn !== null && (
                <p className="shop__timer" role="timer" aria-label="Closes in">
                  Closes in <strong>{formatCountdown(opensIn)}</strong>
                </p>
              )}
            </div>
          </div>
          <ul className="shop__items">
            {shop.stock.map((stock) => (
              <ItemCard
                key={stock.item}
                stock={stock}
                coins={shop.coins}
                busy={busy}
                justBought={bought === stock.item}
                onBuy={() => {
                  buy(stock.item)
                }}
              />
            ))}
          </ul>
        </>
      )}
      <FormError message={actionError} />
      {shop && <Inventory shop={shop} busy={busy} onUseDoubleCoins={useDoubleCoins} />}
    </section>
  )
}

function ItemCard({
  stock,
  coins,
  busy,
  justBought,
  onBuy,
}: {
  stock: Stock
  coins: number
  busy: boolean
  justBought: boolean
  onBuy: () => void
}) {
  const item = ITEMS[stock.item]
  const full = stock.owned >= stock.max_owned
  const short = coins < stock.price
  return (
    <li className="card shop-item">
      {justBought && <Burst />}
      <Icon name={item.icon} size={72} />
      <h3>{item.name}</h3>
      <p className="muted">{item.about}</p>
      <p className="shop-item__owned">
        You have {stock.owned} of {stock.max_owned}
      </p>
      <button
        type="button"
        className="quest__claim shop-item__buy"
        disabled={busy || full || short}
        onClick={onBuy}
      >
        Buy <Icon name="coin" size={20} /> {stock.price.toLocaleString()}
      </button>
      {full ? (
        <p className="muted">You have as many as you can keep.</p>
      ) : (
        short && (
          <p className="muted">{(stock.price - coins).toLocaleString()} more coins needed.</p>
        )
      )}
    </li>
  )
}

/** What you own, every day: freezes work by themselves; double coins start when you say. */
function Inventory({
  shop,
  busy,
  onUseDoubleCoins,
}: {
  shop: Shop
  busy: boolean
  onUseDoubleCoins: () => void
}) {
  const left = useCountdown(shop.double_coins_until)
  const freezes = shop.stock.find((s) => s.item === 'streak_freeze')?.owned ?? 0
  const doubles = shop.stock.find((s) => s.item === 'double_coins')?.owned ?? 0
  const names = shop.stock.find((s) => s.item === 'name_change')?.owned ?? 0
  const running = left !== null && left > 0
  return (
    <section className="card inventory" aria-labelledby="inventory-heading">
      <h3 id="inventory-heading">Your inventory</h3>
      <ul className="inventory__list">
        <li>
          <Icon name="torch" size={40} />
          <span>
            <strong>Streak freezes: {freezes}</strong>
            <span className="muted"> · used by themselves on a missed day</span>
          </span>
        </li>
        <li>
          <Icon name="double_coins" size={40} />
          <span>
            <strong>Double coins: {doubles}</strong>
            {running && (
              <span className="inventory__running">
                {' '}
                · 2× coins for <strong>{formatCountdown(left)}</strong>
              </span>
            )}
          </span>
          {doubles > 0 && (
            <button type="button" className="primary" disabled={busy} onClick={onUseDoubleCoins}>
              {running ? 'Add 30 min' : 'Use now'}
            </button>
          )}
        </li>
        <li>
          <Icon name="name_badge" size={40} />
          <span>
            <strong>Username changes: {names}</strong>
            <span className="muted"> · use it in Settings</span>
          </span>
          {names > 0 && (
            <Link className="button-link secondary" to="/settings">
              Settings
            </Link>
          )}
        </li>
      </ul>
    </section>
  )
}

function Market({ open }: { open: boolean }) {
  return (
    <div
      className="market"
      role="img"
      aria-label={
        open
          ? 'A busy desert market; the merchant’s stall is open'
          : 'A quiet desert market at dusk; one stall is shut'
      }
    >
      <span className="market__moon">
        <Icon name="crescent_moon" size={56} />
      </span>
      <span className="market__dune market__dune--back" />
      <span className="market__dune market__dune--front" />
      <span className="market__palm market__palm--left">
        <Icon name="palm_tree" size={110} />
      </span>
      <span className="market__palm market__palm--right">
        <Icon name="palm_tree" size={90} />
      </span>

      <div className="market__stalls">
        <Stall stripe="red">
          <Icon name="amphora" size={44} />
          <Icon name="pot" size={40} />
        </Stall>
        {open ? (
          <Stall stripe="blue">
            <Icon name="torch" size={44} />
            <Icon name="double_coins" size={44} />
          </Stall>
        ) : (
          <Stall stripe="blue" closed>
            <Icon name="door" size={48} />
          </Stall>
        )}
        <Stall stripe="green">
          <Icon name="diya_lamp" size={40} />
          <Icon name="coin" size={34} />
        </Stall>
      </div>

      <span className="market__camel">
        <Icon name="camel" size={84} />
      </span>
    </div>
  )
}

function Stall({
  stripe,
  closed = false,
  children,
}: {
  stripe: 'red' | 'blue' | 'green'
  closed?: boolean
  children: React.ReactNode
}) {
  return (
    <div className={`stall stall--${stripe}${closed ? ' stall--closed' : ''}`}>
      <span className="stall__awning" />
      <span className="stall__front">
        {children}
        {closed && <span className="stall__sign">Back soon</span>}
      </span>
    </div>
  )
}
