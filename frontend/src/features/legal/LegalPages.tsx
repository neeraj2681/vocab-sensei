import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { usePageTitle } from '../../components/usePageTitle'

const CONTACT = 'sensei@vocabsensei.win'
const UPDATED = '9 November 2026'

/** Terms of use, privacy policy and copyright pages: readable without an account. */
function LegalPage({
  title,
  tabTitle = title,
  children,
}: {
  title: string
  tabTitle?: string
  children: ReactNode
}) {
  usePageTitle(tabTitle)
  return (
    <article className="legal">
      <p>
        <Link to="/">← Vocab Sensei</Link>
      </p>
      <h1>{title}</h1>
      <p className="muted">Last updated {UPDATED}</p>
      {children}
      <LegalLinks />
    </article>
  )
}

function Contact() {
  return <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
}

/** Links to the three pages, for page footers. */
export function LegalLinks() {
  return (
    <nav className="legal-links" aria-label="Legal">
      <Link to="/terms">Terms of use</Link>
      <Link to="/privacy">Privacy policy</Link>
      <Link to="/copyright">Copyright &amp; takedown</Link>
    </nav>
  )
}

export function TermsPage() {
  return (
    <LegalPage title="Terms of use">
      <p>
        Vocab Sensei (vocabsensei.win) helps you learn the harder words of the books you read. It is
        a free service run by an individual in India. By creating an account you agree to these
        terms. Questions: <Contact />.
      </p>

      <h3>Your account</h3>
      <ul>
        <li>Use your own email address and keep your password to yourself.</li>
        <li>
          You must be 18 or older, or use Vocab Sensei with the permission of a parent or guardian.
        </li>
        <li>
          Pick a username that isn’t offensive and doesn’t pretend to be someone else. We may change
          or remove one that is.
        </li>
      </ul>

      <h3>Books you upload</h3>
      <ul>
        <li>
          Upload only books you own a copy of or have the right to use, such as an ebook you bought
          or a public-domain text. Never upload pirated copies or anything that is illegal to share
          or possess where you live or in India.
        </li>
        <li>
          When you upload a book, our server reads it to build your word list and then{' '}
          <strong>deletes the file</strong>. We keep only the list of words, the chapter titles, one
          short sentence per word and a small cover picture, and only you can see them.
        </li>
        <li>
          You keep every right you have in the book. You allow us to process it for this purpose
          only.
        </li>
        <li>
          If we receive a valid complaint about a book, we remove its word data from the account.
          Accounts that repeatedly upload infringing books will be closed (see{' '}
          <Link to="/copyright">Copyright &amp; takedown</Link>).
        </li>
      </ul>

      <h3>Using Vocab Sensei fairly</h3>
      <ul>
        <li>
          Don’t try to break, overload or copy the service, read other people’s data, or get around
          its limits.
        </li>
        <li>Be kind in anything other people can see, like your username and photo.</li>
      </ul>

      <h3>Leaderboard, profiles and friends</h3>
      <p>
        You are not on the leaderboard unless you turn it on in Settings. When it’s on, other people
        can see your username, photo and learning stats, and the books you’re reading if you allow
        that. Friends can find you by your exact email address or username.
      </p>

      <h3>Coins and the Shop</h3>
      <p>
        Coins, streak freezes and other Shop items are part of the game. They have no money value,
        can’t be bought, sold or exchanged, and may change.
      </p>

      <h3>The service</h3>
      <ul>
        <li>
          Vocab Sensei is provided as it is, without guarantees. We work to keep it running and your
          data safe, but it may sometimes be unavailable, and features may change or end.
        </li>
        <li>
          To the extent the law allows, we aren’t liable for indirect losses or for losses caused by
          using or being unable to use the service.
        </li>
        <li>
          You can delete your account at any time in Settings. We may suspend or close an account
          that breaks these terms.
        </li>
      </ul>

      <h3>Changes and law</h3>
      <p>
        If we change these terms, we’ll update this page, and email you about important changes.
        These terms are governed by the laws of India.
      </p>
    </LegalPage>
  )
}

export function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy">
      <p>
        This page explains what Vocab Sensei collects, why, and what you can do about it. We don’t
        sell your data, show ads or use tracking or analytics tools. Questions or requests:{' '}
        <Contact />.
      </p>

      <h3>What we collect</h3>
      <ul>
        <li>
          <strong>Account:</strong> your email address, username and password. The password is
          stored only as a secure hash (Argon2), never as text.
        </li>
        <li>
          <strong>Optional profile:</strong> gender (for the default picture) and a photo, if you
          add one.
        </li>
        <li>
          <strong>Learning:</strong> your answers, word progress, coins, streaks, quests, Shop
          items, daily goal, friends, reminder settings and time zone.
        </li>
        <li>
          <strong>Books:</strong> the word list, chapter titles, one short sentence per word and a
          cover picture for each book you upload. The book file itself is deleted once it has been
          read.
        </li>
        <li>
          <strong>Speech practice:</strong> when you use “Say it”, the recording is sent to our
          server to recognise the word and is not stored.
        </li>
        <li>
          <strong>Reminders:</strong> if you turn on browser notifications, the address your browser
          gives us for sending them.
        </li>
        <li>
          <strong>Newsletter:</strong> whether you chose to get it, and when. Only if you tick the
          box at sign-up or turn it on in Settings.
        </li>
        <li>
          <strong>Technical:</strong> your IP address is kept briefly in memory to limit repeated
          login and email attempts. Server logs are kept for a short time to fix problems.
        </li>
      </ul>

      <h3>Why we use it</h3>
      <p>
        To run your account and quizzes, to send the emails you ask for (address confirmation,
        password reset, reminders and recaps), to send the newsletter if you chose it, and to
        protect the service from abuse.
      </p>

      <h3>Cookies and storage</h3>
      <p>
        One essential cookie keeps you logged in. Your browser also stores a few preferences on your
        device, such as theme and sound. Nothing is used for advertising or tracking.
      </p>

      <h3>Who else handles it</h3>
      <ul>
        <li>Oracle Cloud hosts our server and database in Mumbai, India.</li>
        <li>
          Brevo sends our emails and, if you subscribe, keeps your name and email address on the
          newsletter list until you unsubscribe or delete your account.
        </li>
        <li>Cloudflare provides the domain name and forwards email sent to us.</li>
        <li>
          If you turn on notifications, your browser’s push service (from Apple, Google or Mozilla)
          delivers them.
        </li>
        <li>
          Other users see your username, photo and stats only if you turn on the leaderboard, and
          your books only if you also allow that.
        </li>
      </ul>

      <h3>How long we keep it</h3>
      <p>
        For as long as you have an account. When you delete your account (Settings → Delete
        account), your data is deleted straight away; copies in our daily backups are gone within 7
        days.
      </p>

      <h3>Your rights</h3>
      <p>
        Under India’s Digital Personal Data Protection Act, 2023 (and the GDPR if you are in the
        EU), you can:
      </p>
      <ul>
        <li>see your data: download a copy from Me → Backup;</li>
        <li>correct it: in Settings;</li>
        <li>delete it: delete your account in Settings, or ask us;</li>
        <li>
          withdraw consent: for example, turn off reminders, the leaderboard or the newsletter;
        </li>
        <li>
          nominate someone to act for you, and complain to us or to the Data Protection Board.
        </li>
      </ul>
      <p>
        Write to <Contact /> for anything else. We acknowledge messages within 24 hours and resolve
        them within 15 days.
      </p>

      <h3>Children</h3>
      <p>
        Vocab Sensei is for people aged 18 and over, or younger people using it with a parent’s or
        guardian’s permission.
      </p>

      <h3>Security</h3>
      <p>
        Everything travels over HTTPS, passwords are hashed, uploaded books are deleted after
        reading, and access to the server is limited to its operator.
      </p>
    </LegalPage>
  )
}

export function CopyrightPage() {
  return (
    <LegalPage title="Copyright & takedown" tabTitle="Copyright and takedown">
      <p>
        We respect authors’ and publishers’ rights. Uploaded books are private to the person who
        uploaded them: the file is deleted once it has been read, and only a word list with one
        short sentence per word remains, visible to that person alone. The built-in classics come
        from Project Gutenberg and are in the public domain.
      </p>

      <h3>Report a book</h3>
      <p>
        If you believe a book on Vocab Sensei infringes your copyright, or is otherwise unlawful,
        email <Contact /> with:
      </p>
      <ul>
        <li>your name and how to reach you;</li>
        <li>the work concerned, and whether you own it or act for the owner;</li>
        <li>what you found and where (for example, a username or a book title on a profile);</li>
        <li>
          a statement that you believe in good faith the use isn’t authorised and that your notice
          is accurate.
        </li>
      </ul>

      <h3>What happens next</h3>
      <ul>
        <li>We acknowledge your notice within 24 hours.</li>
        <li>
          If it’s valid, we remove the book’s data from the account, usually within 36 hours, and
          tell the account holder.
        </li>
        <li>Accounts that repeatedly upload infringing books are closed.</li>
        <li>
          If your book was removed and you think that was a mistake, reply to our email explaining
          why. We’ll look again.
        </li>
      </ul>

      <h3>Grievances</h3>
      <p>
        Complaints about content or how we handle your data go to our grievance contact at{' '}
        <Contact />. We resolve them within 15 days.
      </p>
    </LegalPage>
  )
}
