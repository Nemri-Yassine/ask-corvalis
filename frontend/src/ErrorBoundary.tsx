import { Component, type ReactNode } from 'react'

// If a bug crashes the page while drawing it, show a friendly message
// instead of a blank screen. (React only supports this with a class component.)
export default class ErrorBoundary extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false }

  static getDerivedStateFromError() {
    return { crashed: true }
  }

  componentDidCatch(error: unknown) {
    console.error('Ask Corvalis crashed:', error)
  }

  render() {
    if (!this.state.crashed) return this.props.children
    return (
      <main className="chat">
        <div className="answer error" role="alert">
          Something went wrong on this page.
          <button type="button" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      </main>
    )
  }
}
