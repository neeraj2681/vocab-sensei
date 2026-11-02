import { useEffect, useState } from 'react'
import { quizApi } from '../../api/quiz'
import { Icon } from '../../components/Icon'

/** The market where coins will buy things. The merchant hasn't arrived yet. */
export function ShopPage() {
  const [coins, setCoins] = useState<number | null>(null)

  useEffect(() => {
    let current = true
    quizApi
      .stats()
      .then((stats) => {
        if (current) setCoins(stats.total)
      })
      .catch(() => undefined) // the market still shows; only the balance is missing
    return () => {
      current = false
    }
  }, [])

  return (
    <section className="shop">
      <div className="shop__head">
        <h2>Shop</h2>
        {coins !== null && (
          <span className="stat-pill" title="Your coins">
            <Icon name="coin" size={22} /> {coins.toLocaleString()} coins
          </span>
        )}
      </div>

      <div
        className="market"
        role="img"
        aria-label="A quiet desert market at dusk; one stall is shut"
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
          <Stall stripe="blue" closed>
            <Icon name="door" size={48} />
          </Stall>
          <Stall stripe="green">
            <Icon name="diya_lamp" size={40} />
            <Icon name="coin" size={34} />
          </Stall>
        </div>

        <span className="market__camel">
          <Icon name="camel" size={84} />
        </span>
      </div>

      <div className="card shop__notice">
        <Icon name="hourglass" size={48} />
        <div>
          <h3>The merchant isn’t here yet</h3>
          <p className="muted">
            Keep earning coins in the quiz. When the merchant arrives you’ll be able to buy things
            like a streak freeze or another name change.
          </p>
        </div>
      </div>
    </section>
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
