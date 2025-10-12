import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Simulation } from '../types'
import './QuestionsListPage.css'

export default function QuestionsListPage() {
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [loading, setLoading] = useState(true)
  const [enriching, setEnriching] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    loadSimulations()
  }, [])

  const loadSimulations = async () => {
    console.log('📋 Loading simulations list...')
    try {
      const result = await api.listSimulations()
      console.log('✅ Simulations loaded:', result.simulations?.length || 0)
      setSimulations(result.simulations || [])
    } catch (err) {
      console.error('❌ Failed to load simulations:', err)
    } finally {
      console.log('✅ Setting loading to false')
      setLoading(false)
    }
  }

  const handleEnrich = async (simulationId: string) => {
    setEnriching(simulationId)
    try {
      await api.enrichSimulation(simulationId)
      // Reload to get updated status
      await loadSimulations()
    } catch (err) {
      console.error('Failed to enrich:', err)
      alert('Failed to enrich simulation')
    } finally {
      setEnriching(null)
    }
  }

  const handleSimulate = (simulationId: string) => {
    navigate(`/simulation/${simulationId}`)
  }

  const handleRewatch = (simulationId: string) => {
    navigate(`/simulation/${simulationId}`)
  }

  const getButtonForStatus = (sim: Simulation) => {
    if (sim.status === 'created') {
      return (
        <button
          className={`action-button enrich ${enriching === sim.simulation_id ? 'spinning-icon' : ''}`}
          onClick={() => handleEnrich(sim.simulation_id)}
          disabled={enriching === sim.simulation_id}
        >
          {enriching === sim.simulation_id ? '' : 'enrich'}
        </button>
      )
    }

    if (sim.status === 'enriched' || sim.status === 'running') {
      return (
        <button
          className="action-button simulate"
          onClick={() => handleSimulate(sim.simulation_id)}
        >
          {sim.status === 'running' ? 'continue' : 'simulate'}
        </button>
      )
    }

    if (sim.status === 'completed') {
      return (
        <button
          className="action-button rewatch"
          onClick={() => handleRewatch(sim.simulation_id)}
        >
          rewatch
        </button>
      )
    }

    return null
  }

  if (loading) {
    return (
      <div className="questions-list-page">
        <div className="loading">Loading...</div>
      </div>
    )
  }

  return (
    <div className="questions-list-page">
      <button 
        className="nav-button"
        onClick={() => navigate('/')}
      >
        ← New
      </button>

      <div className="questions-container">
        <div className="questions-content">
          <h1 className="page-title">Questions</h1>

          <div className="simulations-list">
          {simulations.map((sim) => (
            <div key={sim.simulation_id} className="simulation-card">
              <div className="card-content">
                <h2 className="question-text">{sim.question}</h2>
                <div className="metadata">
                  <span className={`status status-${sim.status}`}>
                    {sim.status}
                  </span>
                  <span className="meta-item">
                    {(sim as any).actors_count || sim.actors?.length || 0} actors
                  </span>
                  <span className="meta-item">
                    {sim.simulation_duration} {sim.time_unit}s
                  </span>
                </div>
              </div>
              <div className="card-action">
                {getButtonForStatus(sim)}
              </div>
            </div>
          ))}

          {simulations.length === 0 && (
            <div className="empty-state">
              <p>No simulations yet</p>
              <button 
                className="new-simulation-button"
                onClick={() => navigate('/')}
              >
                Create your first simulation
              </button>
            </div>
          )}
          </div>
        </div>

        <div className="illustration">
          <svg viewBox="0 0 400 500" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Head */}
            <circle cx="200" cy="140" r="60" fill="#bbb"/>
            {/* Body */}
            <ellipse cx="200" cy="320" rx="100" ry="140" fill="#ccc"/>
            {/* Speech bubble */}
            <rect x="60" y="60" width="100" height="60" rx="30" fill="#999"/>
            <path d="M150 100 L170 130 L150 120 Z" fill="#999"/>
          </svg>
        </div>

        <button 
          className="floating-new-button"
          onClick={() => navigate('/')}
          title="New question"
        >
          +
        </button>
      </div>
    </div>
  )
}
