import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Answer from './Answer'
import Filters from './Filters'
import { SendIcon } from './icons'
import {
  ask,
  FriendlyError,
  getFilterChoices,
  type AskResponse,
  type FilterChoices,
  type ProjectFilters,
  type Scope,
} from './api'

// One exchange in the conversation: the question, then a result, an error, or "loading".
type Turn = {
  id: number
  question: string
  result?: AskResponse
  error?: string
}

// Each mode is its own conversation, with its own intro and suggestions.
const MODES: Record<Scope, { intro: string; placeholder: string; suggestions: string[] }> = {
  rules: {
    intro: 'Leave, expenses, IT, purchasing, your first days… I answer from the official Corvalis policies.',
    placeholder: 'Ask about a company rule…',
    suggestions: [
      'How many days of annual leave do I get?',
      "What's the mileage rate?",
      'I lost my laptop, what do I do?',
      'Do I need a quote for a €3,000 purchase?',
      'Can I work from home?',
      "What should I do if I'm sick?",
    ],
  },
  projects: {
    intro: 'Describe what you are working on and I will find similar Corvalis projects, with who led them and where the files are.',
    placeholder: 'Describe the project you are looking for…',
    suggestions: [
      'Have we designed a timber footbridge before?',
      'Hospital extension in Liège',
      'CLT office building',
      'Post-tensioned car park',
      'School renovation with heat pumps',
    ],
  },
}

const MAX_LENGTH = 500
const NO_FILTERS: ProjectFilters = { projectType: '', yearFrom: '', yearTo: '' }

// "Looking it up…", then a reassurance if the AI is slow (it can take up to 30 s).
function Loading() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 8000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <div className="msg assistant">
      <span className="avatar" aria-hidden="true">C</span>
      <div className="card loading" aria-live="polite">
        {slow ? 'Still working, this one is taking a little longer' : 'Looking it up'}
        <span className="dots" />
      </div>
    </div>
  )
}

type Props = { scope: Scope; onBusyChange: (busy: boolean) => void }

export default function Chat({ scope, onBusyChange }: Props) {
  const [turns, setTurns] = useState<Record<Scope, Turn[]>>({ rules: [], projects: [] })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ProjectFilters>(NO_FILTERS)
  const [choices, setChoices] = useState<FilterChoices | null>(null)
  const lastTurnRef = useRef<HTMLLIElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const mode = MODES[scope]
  const current = turns[scope]

  // Show the newest question at the top, so a long answer is read from its start.
  useEffect(() => {
    lastTurnRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [current])

  // Load the filter options (types, years) once.
  useEffect(() => {
    getFilterChoices().then(setChoices)
  }, [])

  // Let the question box grow with its text (up to a limit set in CSS).
  useEffect(() => {
    const box = inputRef.current
    if (!box) return
    box.style.height = 'auto'
    box.style.height = `${box.scrollHeight}px`
  }, [input])

  function setBusy(busy: boolean) {
    setLoading(busy)
    onBusyChange(busy)
  }

  function updateTurn(id: number, change: Partial<Turn>) {
    setTurns((all) => ({
      ...all,
      [scope]: all[scope].map((turn) => (turn.id === id ? { ...turn, ...change } : turn)),
    }))
  }

  // Ask a new question, or (with retryId) ask a failed one again in place.
  async function send(question: string, retryId?: number) {
    question = question.trim()
    if (!question || loading) return

    const id = retryId ?? Date.now()
    if (retryId) {
      updateTurn(id, { error: undefined, result: undefined })
    } else {
      setTurns((all) => ({ ...all, [scope]: [...all[scope], { id, question }] }))
      setInput('')
    }
    setBusy(true)

    try {
      const result = await ask(question, scope, filters)
      updateTurn(id, { result })
    } catch (e) {
      const error = e instanceof FriendlyError ? e.message : 'Something went wrong. Please try again.'
      updateTurn(id, { error })
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  // Enter sends, Shift+Enter adds a new line.
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <>
      <main className="chat">
        {scope === 'projects' && choices && (
          <Filters choices={choices} filters={filters} onChange={setFilters} />
        )}

        {current.length === 0 && (
          <section className="welcome">
            <h1>Hi 👋 Ask me about company rules or past projects</h1>
            <p>{mode.intro}</p>
            <div className="chips">
              {mode.suggestions.map((q) => (
                <button key={q} type="button" className="chip" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </section>
        )}

        <ol className="turns">
          {current.map((turn, i) => (
            <li key={turn.id} ref={i === current.length - 1 ? lastTurnRef : undefined}>
              <div className="msg user">
                <p className="bubble">{turn.question}</p>
              </div>

              {turn.result && <Answer result={turn.result} />}

              {turn.error && (
                <div className="msg assistant">
                  <span className="avatar" aria-hidden="true">C</span>
                  <div className="card error" role="alert">
                    <p>{turn.error}</p>
                    <button type="button" className="btn-secondary" onClick={() => send(turn.question, turn.id)}>
                      Try again
                    </button>
                  </div>
                </div>
              )}

              {!turn.result && !turn.error && <Loading />}
            </li>
          ))}
        </ol>
      </main>

      <div className="composer-wrap">
        <form className="composer" onSubmit={onSubmit}>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={mode.placeholder}
            aria-label="Your question"
            maxLength={MAX_LENGTH}
            autoFocus
          />
          <button type="submit" className="send" aria-label="Send question" disabled={loading || !input.trim()}>
            <SendIcon />
          </button>
        </form>
        <p className="composer-hint">Enter to send · Shift+Enter for a new line</p>
      </div>
    </>
  )
}
