import { useState, useEffect } from 'react'

function ScoreBadge({ score }) {
  const cls =
    score >= 80
      ? 'bg-green-100 text-green-700'
      : score >= 60
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-red-100 text-red-600'
  return (
    <span className={`text-sm font-bold px-2.5 py-0.5 rounded-full ${cls}`}>{score}</span>
  )
}

function StatusPill({ status }) {
  const styles = {
    pending: 'bg-gray-100 text-gray-500',
    approved: 'bg-green-100 text-green-700',
    skipped: 'bg-red-50 text-red-500',
    submitted: 'bg-blue-100 text-blue-700',
  }
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
        styles[status] || styles.pending
      }`}
    >
      {status}
    </span>
  )
}

function DraftCard({ draft, onApprove, onEdit, onSkip }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(draft.draft_paragraph)

  const handleSave = () => {
    onEdit(draft.id, text)
    setEditing(false)
  }

  const isActionable = draft.status !== 'submitted'

  return (
    <div
      className={`bg-white rounded-xl shadow-sm border-2 transition-colors ${
        draft.status === 'approved'
          ? 'border-green-200'
          : draft.status === 'skipped'
          ? 'border-red-100 opacity-60'
          : 'border-gray-100'
      }`}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-gray-900 text-sm">{draft.company_name}</h3>
            <span className="text-gray-300">·</span>
            <span className="text-sm text-gray-600 truncate">{draft.job_title}</span>
            {draft.company_batch && (
              <span className="text-xs bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded font-semibold">
                {draft.company_batch}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400 flex-wrap">
            <span>{draft.role_type}</span>
            {draft.remote && <span className="text-green-600 font-medium">Remote</span>}
            {draft.location && <span>{draft.location}</span>}
            {draft.company_industry && <span>{draft.company_industry}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <ScoreBadge score={draft.match_score} />
          <StatusPill status={draft.status} />
        </div>
      </div>

      {/* Match Reasoning */}
      <div className="px-5 py-3 bg-gray-50 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Match Reasoning
        </p>
        <p className="text-xs text-gray-600 leading-relaxed">{draft.match_reasoning}</p>
      </div>

      {/* Draft Paragraph */}
      <div className="px-5 py-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Application Draft
        </p>
        {editing ? (
          <div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none leading-relaxed"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleSave}
                className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
              >
                Save &amp; Approve
              </button>
              <button
                onClick={() => {
                  setEditing(false)
                  setText(draft.draft_paragraph)
                }}
                className="text-gray-500 hover:text-gray-700 px-3 py-1.5 text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-700 leading-relaxed">{draft.draft_paragraph}</p>
        )}
      </div>

      {/* Actions */}
      {!editing && isActionable && (
        <div className="px-5 py-3 border-t border-gray-100 flex items-center gap-2">
          <a
            href={draft.job_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:underline mr-auto"
          >
            View Job →
          </a>
          {draft.status !== 'approved' && (
            <button
              onClick={() => onApprove(draft.id)}
              className="bg-green-500 hover:bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              Approve
            </button>
          )}
          <button
            onClick={() => setEditing(true)}
            className="bg-blue-50 hover:bg-blue-100 text-blue-600 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
          >
            Edit
          </button>
          {draft.status !== 'skipped' && (
            <button
              onClick={() => onSkip(draft.id)}
              className="bg-red-50 hover:bg-red-100 text-red-600 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              Skip
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function Review() {
  const [drafts, setDrafts] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitMsg, setSubmitMsg] = useState('')

  const loadDrafts = () => {
    fetch('/api/drafts')
      .then((r) => r.json())
      .then((d) => {
        setDrafts(d)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    loadDrafts()
  }, [])

  const handleApprove = async (id) => {
    await fetch(`/api/drafts/${id}/approve`, { method: 'POST' })
    setDrafts((prev) => prev.map((d) => (d.id === id ? { ...d, status: 'approved' } : d)))
  }

  const handleEdit = async (id, text) => {
    await fetch(`/api/drafts/${id}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_paragraph: text }),
    })
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, draft_paragraph: text, status: 'approved' } : d))
    )
  }

  const handleSkip = async (id) => {
    await fetch(`/api/drafts/${id}/skip`, { method: 'POST' })
    setDrafts((prev) => prev.map((d) => (d.id === id ? { ...d, status: 'skipped' } : d)))
  }

  const handleSubmit = async (dryRun = false) => {
    setSubmitting(true)
    setSubmitMsg('')
    try {
      const res = await fetch('/api/pipeline/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: dryRun }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Submit failed')
      setSubmitMsg(dryRun ? 'Dry run started — check Pipeline page for progress.' : 'Submission started — check Pipeline page for progress.')
      loadDrafts()
    } catch (err) {
      setSubmitMsg(`Error: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  const counts = {
    all: drafts.length,
    pending: drafts.filter((d) => d.status === 'pending').length,
    approved: drafts.filter((d) => d.status === 'approved').length,
    skipped: drafts.filter((d) => d.status === 'skipped').length,
    submitted: drafts.filter((d) => d.status === 'submitted').length,
  }

  const filtered = filter === 'all' ? drafts : drafts.filter((d) => d.status === filter)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Review Drafts</h2>
          <p className="text-gray-500 mt-1 text-sm">
            Approve, edit, or skip application drafts before submission
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {counts.approved > 0 && (
            <div className="flex gap-2">
              <button
                onClick={() => handleSubmit(true)}
                disabled={submitting}
                className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 px-4 py-2 rounded-lg font-medium text-sm transition-colors"
              >
                {submitting ? '...' : 'Dry Run'}
              </button>
              <button
                onClick={() => handleSubmit(false)}
                disabled={submitting}
                className="bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white px-5 py-2 rounded-lg font-medium text-sm transition-colors"
              >
                {submitting ? 'Submitting...' : `Submit ${counts.approved} Approved`}
              </button>
            </div>
          )}
          {submitMsg && (
            <p
              className={`text-xs ${
                submitMsg.startsWith('Error') ? 'text-red-500' : 'text-green-600'
              }`}
            >
              {submitMsg}
            </p>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {[
          ['all', 'All'],
          ['pending', 'Pending'],
          ['approved', 'Approved'],
          ['skipped', 'Skipped'],
          ['submitted', 'Submitted'],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              filter === key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
            {counts[key] > 0 && (
              <span className="ml-1.5 text-xs text-gray-400">{counts[key]}</span>
            )}
          </button>
        ))}
      </div>

      {/* Draft list */}
      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center border border-gray-100">
          {drafts.length === 0 ? (
            <>
              <p className="text-gray-500 font-medium">No drafts yet</p>
              <p className="text-gray-400 text-sm mt-1">
                Run the pipeline to generate application drafts
              </p>
            </>
          ) : (
            <p className="text-gray-400 text-sm">No {filter} drafts</p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((draft) => (
            <DraftCard
              key={draft.id}
              draft={draft}
              onApprove={handleApprove}
              onEdit={handleEdit}
              onSkip={handleSkip}
            />
          ))}
        </div>
      )}
    </div>
  )
}
