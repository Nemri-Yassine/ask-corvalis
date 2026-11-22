import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Answer from './Answer'
import Filters from './Filters'
import Progress, { type ProgressState } from './Progress'
import { SendIcon, StopIcon } from './icons'
import {
  askStream,
  FriendlyError,
  getFilterChoices,
  type AskResponse,
  type FilterChoices,
  type ProjectFilters,
  type Scope,
} from './api'

// One exchange in the conversation: the question, then live progress, and
// finally a result or an error.
type Turn = {
  id: number
  question: string
  progress?: ProgressState
  result?: AskResponse
  error?: string
  stopped?: boolean
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

type Props = { scope: Scope; onBusyChange: (busy: boolean) => void }

export default function Chat({ scope, onBusyChange }: Props) {
  const [turns, setTurns] = useState<Record<Scope, Turn[]>>({ rules: [], projects: [] })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ProjectFilters>(NO_FILTERS)
  const [choices, setChoices] = useState<FilterChoices | null>(null)
  const lastTurnRef = useRef<HTMLLIElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null) // lets the Stop button cancel

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
    const progress: ProgressState = { phase: 'searching', text: '', startedAt: Date.now() }
    if (retryId) {
      updateTurn(id, { progress, error: undefined, result: undefined, stopped: false })
    } else {
      setTurns((all) => ({ ...all, [scope]: [...all[scope], { id, question, progress }] }))
      setInput('')
    }
    setBusy(true)
    const controller = new AbortController()
    abortRef.current = controller

    // Progress updates as the server streams: search done -> AI writing -> pieces of text.
    let live = progress
    const show = (change: Partial<ProgressState>) => {
      live = { ...live, ...change }
      updateTurn(id, { progress: live })
    }

    try {
      const result = await askStream(
        question,
        scope,
        filters,
        {
          onSearch: (step) => {
            if (step.ai) show({ phase: 'writing', model: step.model, startedAt: Date.now() })
          },
          onToken: (piece) => show({ text: live.text + piece }),
        },
        controller.signal,
      )
      updateTurn(id, { result, progress: undefined })
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        updateTurn(id, { stopped: true, progress: undefined })
      } else {
        const error = e instanceof FriendlyError ? e.message : 'Something went wrong. Please try again.'
        updateTurn(id, { error, progress: undefined })
      }
    } finally {
      abortRef.current = null
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

              {turn.progress && <Progress progress={turn.progress} scope={scope} />}

              {(turn.error || turn.stopped) && (
                <div className="msg assistant">
                  <span className="avatar" aria-hidden="true">C</span>
                  <div className={`card ${turn.stopped ? 'stopped' : 'error'}`} role="alert">
                    <p>{turn.stopped ? 'You stopped this answer.' : turn.error}</p>
                    <button type="button" className="btn-secondary" onClick={() => send(turn.question, turn.id)}>
                      Try again
                    </button>
                  </div>
                </div>
              )}

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
          {loading ? (
            <button
              type="button"
              className="send stop"
              aria-label="Stop the answer"
              title="Stop"
              onClick={() => abortRef.current?.abort()}
            >
              <StopIcon />
            </button>
          ) : (
            <button type="submit" className="send" aria-label="Send question" disabled={!input.trim()}>
              <SendIcon />
            </button>
          )}
        </form>
        <p className="composer-hint">Enter to send · Shift+Enter for a new line</p>
      </div>
    </>
  )
}
