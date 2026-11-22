import Chat from './Chat'
import HrDashboard from './HrDashboard'
import './App.css'

// Two pages only, so no router library: the URL path decides which one to show.
const isHrPage = window.location.pathname.startsWith('/hr')

export default function App() {
  return (
    <div className="page">
      <header className="header">
        <div className="header-inner">
          <a className="wordmark" href="/">
            <span className="logo" aria-hidden="true">C</span>
            <span>
              <strong>Corvalis</strong> · Ask
            </span>
          </a>
          {isHrPage ? (
            <a className="header-link" href="/">← Back to questions</a>
          ) : (
            <a className="header-link" href="/hr">HR dashboard</a>
          )}
        </div>
      </header>

      {isHrPage ? <HrDashboard /> : <Chat />}
    </div>
  )
}
