import type { CapacitorConfig } from '@capacitor/cli'

// The iPhone app shows the live site (same address, so sign-in cookies just work, and every deploy
// reaches the phone without a rebuild). The address lives in .env.ios.local (not committed):
//   VOCAB_APP_URL=https://your-domain
const url = process.env.VOCAB_APP_URL

const config: CapacitorConfig = {
  appId: 'io.github.neeraj2681.vocabsensei',
  appName: 'Vocab Sensei',
  webDir: 'dist', // a fallback copy; the app loads `url`
  server: url ? { url, cleartext: url.startsWith('http://') } : undefined, // http: only for local tests
  ios: {
    contentInset: 'never',
    backgroundColor: '#f3f8f2', // the page background, behind the status bar
  },
}

export default config
