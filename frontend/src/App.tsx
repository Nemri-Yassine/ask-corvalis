import { useEffect, useRef, useState, type FormEvent } from 'react'
import Answer from './Answer'
import { ask, FriendlyError, type AskResponse, type Scope } from './api'
import './App.css'

// One line of the conversation: the question, then either a result, an error, or "loading".
type Turn = {
  id: number
  question: string
  result?: AskResponse
  error?: string
}

const EXAMPLES: Record<Scope, string[]> = {
  rules: [
    'How many days of annual leave do I get?',
    "What's the mileage rate?",
    'I lost my laptop, what do I do?',
    'Do I need a quote for a €3,000 purchase?',
  ],
  projects: [],
}

const MAX_LENGTH = 500

export default function App() {
  const [scope, setScope] = useState<Scope>('rules')
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Keep the latest message in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  // Ask a new question, or (with retryId) ask a failed one again in place.
  async function send(question: string, retryId?: number) {
    question = question.trim()
    if (!question || loading) return

    const id = retryId ?? Date.now()
    if (retryId) {
      setTurns((t) => t.map((turn) => (turn.id === id ? { id, question } : turn)))
    } else {
      setTurns((t) => [...t, { id, question }])
      setInput('')
    }
    setLoading(true)

    try {
      const result = await ask(question, scope)
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, result } : turn)))
    } catch (e) {
      const error = e instanceof FriendlyError ? e.message : 'Something went wrong, try again.'
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, error } : turn)))
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault() // the form also handles the Enter key
    send(input)
  }

  return (
    <div className="page">
      <header className="header">
        <div className="wordmark">
          <span className="logo" aria-hidden="true">C</span>
          <span>
            <strong>Corvalis</strong> · Ask
          </span>
        </div>
      </header>

      <main className="chat">
        <div className="scope-toggle" role="group" aria-label="What do you want to search?">
          <button
            type="button"
            className={scope === 'rules' ? 'active' : ''}
            aria-pressed={scope === 'rules'}
            onClick={() => setScope('rules')}
          >
            Company rules
          </button>
          <button type="button" disabled title="Coming soon">
            Past projects <small>(soon)</small>
          </button>
        </div>

        {turns.length === 0 && (
          <section className="empty">
            <h1>What would you like to know?</h1>
            <p>Ask about leave, expenses, IT, purchasing or your first days at Corvalis.</p>
            <div className="examples">
              {EXAMPLES[scope].map((q) => (
                <button key={q} type="button" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </section>
        )}

        <ol className="turns">
          {turns.map((turn) => (
            <li key={turn.id}>
              <p className="question">{turn.question}</p>
              {turn.result && <Answer result={turn.result} />}
              {turn.error && (
                <div className="answer error" role="alert">
                  {turn.error}
                  <button type="button" onClick={() => send(turn.question, turn.id)}>
                    Try again
                  </button>
                </div>
              )}
              {!turn.result && !turn.error && (
                <div className="answer loading" aria-live="polite">
                  Looking it up<span className="dots" />
                </div>
              )}
            </li>
          ))}
        </ol>
        <div ref={bottomRef} />
      </main>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          aria-label="Your question"
          maxLength={MAX_LENGTH}
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  )
}
