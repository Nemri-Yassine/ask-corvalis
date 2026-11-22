import { useEffect, useState } from 'react'
import { getStats, type Stats } from './api'

// SQLite stores UTC time as "2026-11-22 10:05:28"; show it in local time.
function formatDate(utc: string | undefined) {
  if (!utc) return ''
  return new Date(utc.replace(' ', 'T') + 'Z').toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function HrDashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState('')

  function load() {
    getStats()
      .then(setStats)
      .catch((e) => setError(e.message))
  }

  useEffect(load, [])

  if (error) {
    return (
      <main className="hr">
        <div className="card error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setError('')
              load()
            }}
          >
            Try again
          </button>
        </div>
      </main>
    )
  }
  if (!stats)
    return (
      <main className="hr">
        <p className="muted">Loading the figures<span className="dots" /></p>
      </main>
    )

  return (
    <main className="hr">
      <h1>HR dashboard</h1>
      <p className="hr-intro">
        Questions about company rules. Unanswered questions and 👎 answers show which policy is
        missing or unclear.
      </p>

      <div className="stats">
        <div className="stat">
          <span className="stat-number">{stats.total}</span>
          <span className="stat-label">questions asked</span>
        </div>
        <div className="stat">
          <span className="stat-number">{stats.answered_pct}%</span>
          <span className="stat-label">answered from the policies</span>
        </div>
        <div className="stat">
          <span className="stat-number">{stats.unanswered_count}</span>
          <span className="stat-label">not answered</span>
        </div>
        <div className="stat">
          <span className="stat-number">{stats.thumbs_down.length}</span>
          <span className="stat-label">answers rated 👎</span>
        </div>
      </div>

      <section className="hr-section">
        <h2>Most asked questions</h2>
        {stats.top_questions.length === 0 ? (
          <p className="empty-note">No questions yet.</p>
        ) : (
          <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th className="num">Times</th>
                <th>Answered?</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_questions.map((q) => (
                <tr key={q.text}>
                  <td>{q.text}</td>
                  <td className="num">{q.count}</td>
                  <td>{q.found ? <span className="pill pill-ok">Yes</span> : <span className="pill pill-warn">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>

      <section className="hr-section">
        <h2>Not answered — missing from the policies?</h2>
        {stats.unanswered.length === 0 ? (
          <p className="empty-note">Every question found an answer.</p>
        ) : (
          <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th className="num">Times</th>
                <th>Last asked</th>
              </tr>
            </thead>
            <tbody>
              {stats.unanswered.map((q) => (
                <tr key={q.text}>
                  <td>{q.text}</td>
                  <td className="num">{q.count}</td>
                  <td className="when">{formatDate(q.last_asked)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>

      <section className="hr-section">
        <h2>Rated 👎 — unclear policy or wrong answer?</h2>
        {stats.thumbs_down.length === 0 ? (
          <p className="empty-note">No negative ratings.</p>
        ) : (
          <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th>Answer given</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {stats.thumbs_down.map((q) => (
                <tr key={q.id}>
                  <td>{q.text}</td>
                  <td className="answer-cell">{q.answer}</td>
                  <td className="when">{formatDate(q.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>
    </main>
  )
}
