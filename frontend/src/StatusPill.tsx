import { useEffect, useState } from 'react'
import { getHealth, type Health } from './api'

const REFRESH_MS = 30_000

// Header pill: is the local AI model running on this computer right now?
export default function StatusPill() {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    const check = () => getHealth().then(setHealth)
    check()
    const timer = setInterval(check, REFRESH_MS)
    return () => clearInterval(timer)
  }, [])

  if (!health) return null // backend not reachable yet: the chat shows its own message

  const label = health.ollama ? `Local AI: ${health.model}` : 'Local AI offline'
  return (
    <span
      className={`status-pill ${health.ollama ? 'on' : 'off'}`}
      role="status"
      title={
        health.ollama
          ? `Answers are written by ${health.model}, running on this computer. Nothing is sent to the internet.`
          : 'The local AI model is not running. You still get answers straight from the documents.'
      }
    >
      <span className="status-dot" aria-hidden="true" />
      <span className="status-label">{label}</span>
    </span>
  )
}
