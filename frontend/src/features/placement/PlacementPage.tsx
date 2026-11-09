import { useNavigate } from 'react-router'
import { PlacementCheck } from './PlacementCheck'

/** The placement check on its own, from Settings: take it again any time. */
export function PlacementPage() {
  const navigate = useNavigate()
  return (
    <PlacementCheck
      onDone={() => {
        void navigate('/settings')
      }}
      onSkip={() => {
        void navigate('/settings')
      }}
    />
  )
}
