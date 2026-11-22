import { useRef, useState } from 'react'
import type { Project } from './api'
import { copyText } from './clipboard'
import { CheckIcon, CopyIcon, FolderIcon } from './icons'

const euros = new Intl.NumberFormat('en-BE', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export default function ProjectCard({ project: p }: { project: Project }) {
  const [copyLabel, setCopyLabel] = useState('')
  const pathRef = useRef<HTMLElement>(null)

  async function copyPath() {
    // If the browser blocks copying, the path is selected so Ctrl+C works.
    setCopyLabel((await copyText(p.folder_path, pathRef.current)) ? 'Copied' : 'Press Ctrl+C')
    setTimeout(() => setCopyLabel(''), 2500)
  }

  return (
    <article className="project-card">
      <header className="project-head">
        <span className="project-number">{p.number}</span>
        <h3>{p.title}</h3>
      </header>

      <p className="project-meta">
        {p.year} · {p.city} · PM <strong>{p.project_manager}</strong>
      </p>

      <div className="tags">
        <span className="tag tag-type">{p.type}</span>
        {p.materials.split(', ').map((m) => (
          <span key={m} className="tag">
            {m}
          </span>
        ))}
        <span className="tag tag-muted">{p.discipline}</span>
      </div>

      <p className="project-summary">{p.summary}</p>
      <p className="project-client">
        {p.client} · {euros.format(p.budget_eur)}
      </p>

      <div className="folder">
        <FolderIcon size={16} />
        <code ref={pathRef}>{p.folder_path}</code>
        <button type="button" className="btn-ghost" onClick={copyPath} aria-label={`Copy folder path for ${p.number}`}>
          {copyLabel === 'Copied' ? <CheckIcon size={15} /> : <CopyIcon size={15} />}
          {copyLabel || 'Copy path'}
        </button>
      </div>
    </article>
  )
}
