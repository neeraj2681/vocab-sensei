/** Phone vibration on answers: real haptics in the iPhone app (Capacitor), the Vibration API where
there is one (Android), and on iPhones in Safari (iOS 18+), which has no Vibration API, the small
haptic tick Safari gives when a switch is toggled, triggered with a hidden switch. Off when the user
turns it off in Settings. */

import { Capacitor } from '@capacitor/core'
import { Haptics, NotificationType } from '@capacitor/haptics'

export const HAPTICS_STORAGE_KEY = 'vs-haptics'

export function hapticsOn(): boolean {
  try {
    return localStorage.getItem(HAPTICS_STORAGE_KEY) !== 'off'
  } catch {
    return true
  }
}

export function setHapticsOn(on: boolean) {
  try {
    localStorage.setItem(HAPTICS_STORAGE_KEY, on ? 'on' : 'off')
  } catch {
    // storage blocked: the choice lasts until the page closes
  }
}

/** A short buzz for right, a double one for wrong. Must run inside a tap (iPhones need that). */
export function buzz(correct: boolean) {
  if (!hapticsOn()) return
  if (Capacitor.isNativePlatform()) {
    void Haptics.notification({
      type: correct ? NotificationType.Success : NotificationType.Error,
    }).catch(() => undefined)
    return
  }
  if (typeof navigator.vibrate === 'function') {
    try {
      navigator.vibrate(correct ? 30 : [60, 40, 60])
    } catch {
      // vibration blocked: the colours carry the result
    }
    return
  }
  iosTick()
  if (!correct) window.setTimeout(iosTick, 140)
}

function iosTick() {
  try {
    const label = document.createElement('label')
    label.ariaHidden = 'true'
    label.style.cssText = 'position:fixed;opacity:0;pointer-events:none;width:1px;height:1px'
    const input = document.createElement('input')
    input.type = 'checkbox'
    input.setAttribute('switch', '') // Safari's switch control ticks when toggled
    label.append(input)
    document.body.append(label)
    label.click()
    label.remove()
  } catch {
    // not possible here: the colours carry the result
  }
}
