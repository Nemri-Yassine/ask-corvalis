import { useEffect, useState } from 'react'
import './App.css'

type Health = { status: string; ollama: boolean }

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setError(true))
  }, [])

  return (
    <main className="placeholder">
      <h1>Ask Corvalis</h1>
      {error && <p>Server not reachable.</p>}
      {!error && !health && <p>Connecting…</p>}
      {health && (
        <p>
          Server: {health.status} · AI model: {health.ollama ? 'available' : 'offline'}
        </p>
      )}
    </main>
  )
}

export default App
