/** What the app is and how to use it, for visitors who haven't logged in yet. */
export function AppIntro() {
  return (
    <section className="intro" aria-labelledby="intro-title">
      <h2 id="intro-title">How it works</h2>
      <ol className="intro__steps">
        <li>
          <strong>Pick a book.</strong> Upload an EPUB, PDF or TXT, or start with one of the
          classics already on the shelf.
        </li>
        <li>
          <strong>See its harder words</strong>, chapter by chapter, with their meanings.
        </li>
        <li>
          <strong>Take the daily quiz.</strong> Aim for 10 answers a day. Each right answer fills a
          word&apos;s progress; at 100% it&apos;s learned.
        </li>
      </ol>
      <p className="muted">Free. All you need is an email address.</p>
    </section>
  )
}
