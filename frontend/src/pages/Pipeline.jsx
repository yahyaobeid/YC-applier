import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

const STATUS_INFO = {
  idle: { label: 'Idle', cls: 'bg-gray-100 text-gray-600' },
  running: { label: 'Running', cls: 'bg-blue-100 text-blue-700' },
  awaiting_review: { label: 'Awaiting Review', cls: 'bg-yellow-100 text-yellow-700' },
  submitting: { label: 'Submitting', cls: 'bg-orange-100 text-orange-700' },
  complete: { label: 'Complete', cls: 'bg-green-100 text-green-700' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-700' },
}

export default function Pipeline() {
  const [status, setStatus] = useState('idle')
  const [progress, setProgress] = useState([])
  const [dryRun, setDryRun] = useState(false)
  const [aiProvider, setAiProvider] = useState('anthropic')
  const [starting, setStarting] = useState(false)
  const logRef = useRef(null)
  const esRef = useRef(null)
  const navigate = useNavigate()

  // Load current state on mount
  useEffect(() => {
    fetch('/api/pipeline/status')
      .then((r) => r.json())
      .then((data) => {
        setStatus(data.status)
        setProgress(data.progress || [])
      })
      .catch(() => {})

    return () => {
      if (esRef.current) esRef.current.close()
    }
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [progress])

  const connectSSE = () => {
    if (esRef.current) esRef.current.close()
    const es = new EventSource('/api/pipeline/events')
    es.onmessage = (e) => {
      const event = JSON.parse(e.data)
      if (event.type === 'ping') return
      if (event.type === 'init') {
        setStatus(event.status)
        return
      }
      if (event.type === 'status_change') {
        fetch('/api/pipeline/status')
          .then((r) => r.json())
          .then((data) => setStatus(data.status))
      }
      setProgress((prev) => [...prev, event])
    }
    es.onerror = () => es.close()
    esRef.current = es
  }

  const handleStart = async () => {
    setStarting(true)
    setProgress([])
    connectSSE()
    try {
      const res = await fetch('/api/pipeline/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: dryRun, ai_provider: aiProvider }),
      })
      const data = await res.json()
      if (data.error || !res.ok) throw new Error(data.detail || data.error || 'Failed to start')
      setStatus('running')
    } catch (err) {
      setProgress((prev) => [
        ...prev,
        { type: 'error', message: err.message, timestamp: new Date().toISOString() },
      ])
    } finally {
      setStarting(false)
    }
  }

  const info = STATUS_INFO[status] || STATUS_INFO.idle
  const canStart = ['idle', 'complete', 'error'].includes(status)

  return (
    <div className="p-8">
      <div className="mb-7">
        <h2 className="text-2xl font-bold text-gray-900">Pipeline</h2>
        <p className="text-gray-500 mt-1 text-sm">
          Scrape, score, and draft application paragraphs
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Controls */}
        <div className="space-y-4">
          {/* Status */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Status
            </p>
            <span
              className={`inline-flex items-center gap-2 text-sm font-semibold px-3 py-1.5 rounded-full ${info.cls}`}
            >
              {status === 'running' && (
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              )}
              {status === 'submitting' && (
                <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              )}
              {info.label}
            </span>
          </div>

          {/* Options */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 space-y-5">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Options
            </p>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1.5">
                AI Provider
              </label>
              <select
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value)}
                disabled={!canStart}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 disabled:bg-gray-50 disabled:text-gray-400"
              >
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai">OpenAI (GPT-4o)</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Dry Run</p>
                <p className="text-xs text-gray-400 mt-0.5">Scrape &amp; draft, skip submit</p>
              </div>
              <button
                type="button"
                onClick={() => setDryRun((v) => !v)}
                disabled={!canStart}
                className={`relative w-10 h-5 rounded-full transition-colors disabled:opacity-40 ${
                  dryRun ? 'bg-orange-500' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    dryRun ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Action buttons */}
          <div className="space-y-2">
            <button
              onClick={handleStart}
              disabled={!canStart || starting}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-2.5 rounded-lg font-medium text-sm transition-colors"
            >
              {starting ? 'Starting...' : 'Start Pipeline'}
            </button>

            {status === 'awaiting_review' && (
              <button
                onClick={() => navigate('/review')}
                className="w-full bg-yellow-500 hover:bg-yellow-600 text-white py-2.5 rounded-lg font-medium text-sm transition-colors"
              >
                Review Drafts →
              </button>
            )}

            {status === 'complete' && (
              <button
                onClick={() => {
                  setStatus('idle')
                  setProgress([])
                }}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-2.5 rounded-lg font-medium text-sm transition-colors"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Right: Progress Log */}
        <div
          className="col-span-2 bg-gray-950 rounded-xl border border-gray-800 flex flex-col"
          style={{ minHeight: '520px' }}
        >
          {/* Terminal chrome */}
          <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-red-500/80" />
              <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <span className="w-3 h-3 rounded-full bg-green-500/80" />
            </div>
            <span className="text-gray-500 text-xs font-mono ml-2">pipeline.log</span>
          </div>

          <div ref={logRef} className="flex-1 overflow-auto p-5 font-mono text-sm space-y-1.5">
            {progress.length === 0 ? (
              <p className="text-gray-600">$ Waiting to start...</p>
            ) : (
              progress.map((e, i) => (
                <div
                  key={i}
                  className={
                    e.type === 'error'
                      ? 'text-red-400'
                      : e.type === 'status_change'
                      ? 'text-yellow-300 font-semibold'
                      : 'text-gray-300'
                  }
                >
                  <span className="text-gray-600 text-xs mr-3">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                  {e.type === 'error' ? '✗ ' : ''}
                  {e.message}
                </div>
              ))
            )}
            {(status === 'running' || status === 'submitting') && (
              <span className="text-blue-400 animate-pulse">▌</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
