import { useEffect, useState } from 'react'
import type { Scope } from './api'

// What we know while an answer is being prepared.
export type ProgressState = {
  phase: 'searching' | 'writing'
  model?: string
  text: string // the AI's answer so far (streamed)
  startedAt: number
}

// Live progress card: 1. searching the documents, 2. local AI writing (with a timer).
export default function Progress({ progress, scope }: { progress: ProgressState; scope: Scope }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(timer)
  }, [])

  const seconds = Math.max(0, (now - progress.startedAt) / 1000).toFixed(1)
  const writing = progress.phase === 'writing'
  // Hide the raw "NOT_FOUND" marker the model may start with; the final answer replaces it.
  const text = progress.text.trimStart().startsWith('NOT_F') ? '' : progress.text

  return (
    <div className="msg assistant">
      <span className="avatar" aria-hidden="true">C</span>
      <div className="card progress" aria-live="polite">
        <ol className="steps">
          <li className={writing ? 'done' : 'active'}>
            <span aria-hidden="true">🔎</span>
            {scope === 'rules' ? 'Searching company documents' : 'Searching past projects'}
            {writing ? <span className="step-check"> ✓</span> : <span className="dots" />}
          </li>
          {writing && (
            <li className="active">
              <span aria-hidden="true">🧠</span>
              <span>
                Writing answer with local AI ({progress.model}), running on this computer
                <span className="dots" />
              </span>
              <span className="elapsed">{seconds}s</span>
            </li>
          )}
        </ol>
        {text && <p className="answer-text streaming">{text}</p>}
      </div>
    </div>
  )
}
