import { useState } from 'react'
import Chat from './Chat'
import ErrorBoundary from './ErrorBoundary'
import HrDashboard from './HrDashboard'
import type { Scope } from './api'
import './App.css'

// Two pages only, so no router library: the URL path decides which one to show.
const isHrPage = window.location.pathname.startsWith('/hr')

export default function App() {
  const [scope, setScope] = useState<Scope>('rules')
  const [busy, setBusy] = useState(false) // no switching tabs while an answer is coming

  return (
    <div className="page">
      <header className="header">
        <div className="header-inner">
          <a className="wordmark" href="/">
            <span className="logo" aria-hidden="true">
              C
            </span>
            Ask Corvalis
          </a>

          {!isHrPage && (
            <div className="segmented" role="group" aria-label="What do you want to ask about?">
              {(['rules', 'projects'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={scope === s}
                  disabled={busy}
                  onClick={() => setScope(s)}
                >
                  {s === 'rules' ? 'Company rules' : 'Past projects'}
                </button>
              ))}
            </div>
          )}

          <nav className="header-actions">
            {isHrPage ? (
              <a className="header-link" href="/">
                ← Back to questions
              </a>
            ) : (
              <a className="header-link" href="/hr">
                HR dashboard
              </a>
            )}
          </nav>
        </div>
      </header>

      <ErrorBoundary>
        {isHrPage ? <HrDashboard /> : <Chat scope={scope} onBusyChange={setBusy} />}
      </ErrorBoundary>
    </div>
  )
}
