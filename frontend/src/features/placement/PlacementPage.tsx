import { useNavigate } from 'react-router'
import { PlacementCheck } from './PlacementCheck'
import { usePageTitle } from '../../components/usePageTitle'

/** The placement check on its own, from Settings: take it again any time. */
export function PlacementPage() {
  usePageTitle('Your level')
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
