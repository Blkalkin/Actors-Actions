import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Simulation, Round, Actor } from '../types'
import './SimulationPage.css'

interface ActorPosition {
  actor_id: string
  identifier: string
  shape: 'circle' | 'square' | 'triangle'
  x: number
  y: number
  color: string
}

interface FlyingMessage {
  id: string
  fromActorId: string
  toActorId: string
  startTime: number
}

export default function SimulationPage() {
  const { simulationId } = useParams<{ simulationId: string }>()
  const navigate = useNavigate()
  
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [rounds, setRounds] = useState<Round[]>([])
  const [currentRound, setCurrentRound] = useState(0)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [selectedActor, setSelectedActor] = useState<Actor | null>(null)
  const [actorPositions, setActorPositions] = useState<ActorPosition[]>([])
  const [flyingMessages, setFlyingMessages] = useState<FlyingMessage[]>([])

  useEffect(() => {
    loadSimulation()
  }, [simulationId])

  const loadSimulation = async () => {
    if (!simulationId) return
    
    try {
      console.log('🔄 Loading simulation...')
      const [simData, roundsData] = await Promise.all([
        api.getSimulation(simulationId),
        api.getRounds(simulationId)
      ])
      
      console.log('✅ Simulation loaded:', simData.status, 'Rounds:', roundsData.length)
      console.log('📊 Current round:', simData.current_round)
      console.log('📊 Actor states keys:', simData.actor_states ? Object.keys(simData.actor_states) : 'none')
      console.log('📊 Full actor_states:', simData.actor_states)
      
      setSimulation(simData)
      setRounds(roundsData)
      setCurrentRound(simData.current_round)
      
      // Generate random positions for actors
      const positions = generateActorPositions(simData.actors)
      setActorPositions(positions)
      
      // Trigger message animations for the latest COMPLETED round (after page refresh/load)
      // current_round is the round being processed, so look at current_round - 1 for completed data
      const latestCompletedRound = simData.current_round > 0 ? simData.current_round - 1 : 0
      if (latestCompletedRound > 0 && simData.actor_states && simData.actor_states[String(latestCompletedRound)]) {
        setTimeout(() => {
          triggerMessageAnimationsWithData(simData, positions, latestCompletedRound)
        }, 1500) // Delay to let shapes settle before birds fly
      }
      
      console.log('✅ Setting loading to false')
      setLoading(false)
    } catch (err) {
      console.error('Failed to load simulation:', err)
      alert('Failed to load simulation')
      setLoading(false)
    }
  }

  const generateActorPositions = (actors: Actor[]): ActorPosition[] => {
    const shapes: ('circle' | 'square' | 'triangle')[] = ['circle', 'square', 'triangle']
    const colors = ['#000', '#333', '#555', '#666', '#888']
    const positions: ActorPosition[] = []
    const minDistance = 14 // Minimum distance between shapes (in percentage units)

    actors.forEach((actor, index) => {
      let x: number = 0
      let y: number = 0
      let attempts = 0
      let validPosition = false
      
      do {
        x = 10 + Math.random() * 80 // 10% to 90% of canvas width
        y = 10 + Math.random() * 75 // 10% to 85% of canvas height
        attempts++
        
        // Check if position is far enough from all existing positions
        validPosition = positions.every(p => {
          const dx = p.x - x
          const dy = p.y - y
          const distance = Math.sqrt(dx * dx + dy * dy)
          return distance >= minDistance
        })
        
      } while (!validPosition && attempts < 100)

      positions.push({
        actor_id: actor.actor_id || '',
        identifier: actor.identifier,
        shape: shapes[index % shapes.length],
        x,
        y,
        color: colors[index % colors.length]
      })
    })

    return positions
  }

  const handleNextRound = async () => {
    if (!simulationId) return
    
    setProcessing(true)
    try {
      // Start background processing
      await api.processRound(simulationId)
      
      console.log('✅ Round processing started in background')
      
      // Keep processing animation for 5 seconds to give visual feedback
      setTimeout(() => {
        setProcessing(false)
      }, 5000)
      
    } catch (err) {
      console.error('Failed to process round:', err)
      setProcessing(false)
    }
  }

  const triggerMessageAnimationsWithData = (simData: Simulation, positions: ActorPosition[], roundNumber: number) => {
    console.log('🐦 triggerMessageAnimationsWithData called for round:', roundNumber)
    
    if (!simData || !simData.actor_states) {
      console.log('⚠️ No simulation or actor_states')
      return
    }

    const roundKey = String(roundNumber)
    const actorStates = simData.actor_states[roundKey]
    
    if (!actorStates) {
      console.log('⚠️ No actor states for round', roundKey)
      return
    }

    // Create one bird per message flying from sender to receiver
    const newBirds: FlyingMessage[] = []
    let messageCount = 0
    
    Object.entries(actorStates).forEach(([toActorId, state]: [string, any]) => {
      const messages = state.messages_received || []
      messages.forEach((msg: any) => {
        newBirds.push({
          id: `${roundNumber}-msg-${messageCount}-${Date.now()}`,
          fromActorId: msg.from_actor_id,
          toActorId: toActorId,
          startTime: Date.now()
        })
        messageCount++
      })
    })

    if (newBirds.length > 0) {
      console.log(`🐦 Animating ${newBirds.length} bird(s) for messages`)
      console.log('Actor positions available:', positions.map(p => p.actor_id))
      console.log('Sample message IDs:', newBirds[0].fromActorId, '→', newBirds[0].toActorId)
      console.log('Full positions:', positions)
      setFlyingMessages(prev => [...prev, ...newBirds])
      
      // Remove birds right as animation completes (2 seconds)
      setTimeout(() => {
        setFlyingMessages(prev => 
          prev.filter(m => !newBirds.find(nb => nb.id === m.id))
        )
      }, 2500)
    } else {
      console.log('❌ No messages found to animate')
    }
  }

  const renderFlyingMessage = (message: FlyingMessage) => {
    const fromPos = actorPositions.find(p => p.actor_id === message.fromActorId)
    const toPos = actorPositions.find(p => p.actor_id === message.toActorId)
    
    if (!fromPos || !toPos) {
      console.log('⚠️ Cannot find positions for message:', message.fromActorId, '→', message.toActorId)
      return null
    }

    const fromX = fromPos.x
    const fromY = fromPos.y
    const toX = toPos.x
    const toY = toPos.y
    
    // Calculate control point for curved path (curve upward)
    const midX = (fromX + toX) / 2
    const midY = (fromY + toY) / 2 - 10 // Curve upward
    
    return (
      <g key={message.id}>
        {/* Animated "v" bird flying from sender to receiver */}
        <text fontSize="3" fill="#4CAF50" fontWeight="normal" fontFamily="monospace">
          <animateMotion
            dur="2.5s"
            repeatCount="1"
            path={`M ${fromX} ${fromY} Q ${midX} ${midY} ${toX} ${toY}`}
          />
          v
        </text>
      </g>
    )
  }

  const renderShape = (pos: ActorPosition, isActive: boolean) => {
    const size = 60
    const className = `actor-shape ${pos.shape} ${isActive ? 'active' : ''}`
    
    return (
      <div
        key={pos.actor_id}
        className={className}
        style={{
          left: `${pos.x}%`,
          top: `${pos.y}%`,
          position: 'absolute'
        }}
        onClick={() => {
          const actor = simulation?.actors.find(a => a.actor_id === pos.actor_id)
          setSelectedActor(actor || null)
        }}
      >
        {pos.shape === 'circle' && (
          <svg width={size} height={size} viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill={pos.color} />
          </svg>
        )}
        {pos.shape === 'square' && (
          <svg width={size} height={size} viewBox="0 0 100 100">
            <rect x="5" y="5" width="90" height="90" fill={pos.color} />
          </svg>
        )}
        {pos.shape === 'triangle' && (
          <svg width={size} height={size} viewBox="0 0 100 100">
            <polygon points="50,5 95,95 5,95" fill={pos.color} />
          </svg>
        )}
        <div className="actor-label">{pos.identifier}</div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="simulation-page">
        <div className="loading">Loading simulation...</div>
      </div>
    )
  }

  if (!simulation) {
    return (
      <div className="simulation-page">
        <div className="error">Simulation not found</div>
      </div>
    )
  }

  const latestRound = rounds[rounds.length - 1]

  return (
    <div className="simulation-page">
      <button className="back-button" onClick={() => navigate('/questions')}>
        ← Back
      </button>

      <div className="simulation-container">
        {/* Left: Actor Canvas */}
        <div className="actor-canvas">
          <div className="canvas-header">
            <h2>{simulation.question}</h2>
            <div className="round-display">
              {simulation.time_unit} {currentRound}
            </div>
          </div>
          
          <div className="canvas-area">
            {actorPositions.map(pos => 
              renderShape(pos, processing)
            )}
            
            {/* SVG overlay for message animations */}
            <svg 
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
                zIndex: 100
              }}
            >
              {flyingMessages.map(msg => renderFlyingMessage(msg))}
            </svg>
          </div>
        </div>

        {/* Right: World State */}
        <div className="world-state-panel">
          <div className="panel-header">
            <div className={`globe ${processing ? 'spinning' : ''}`}>🌐</div>
            <h3>World State</h3>
          </div>

          <div className="world-content">
            {latestRound ? (
              <>
                <div className="world-summary">
                  <h4>Summary</h4>
                  <p>{latestRound.world_state_summary}</p>
                </div>

                {latestRound.key_changes && latestRound.key_changes.length > 0 && (
                  <div className="world-section">
                    <h4>Key Changes</h4>
                    <ul>
                      {latestRound.key_changes.map((change, i) => (
                        <li key={i}>{change}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {latestRound.action_results && latestRound.action_results.length > 0 && (
                  <div className="world-section">
                    <h4>Action Results</h4>
                    {latestRound.action_results.map((result, i) => {
                      const actor = simulation?.actors.find(a => a.actor_id === result.actor_id)
                      const actorName = actor?.identifier || result.actor_id
                      return (
                        <div key={i} className="action-result">
                          <strong>{actorName}:</strong> {result.action}
                          <div className="result-outcome">{result.outcome}</div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <p>No rounds yet. Click "Next" to start the simulation.</p>
              </div>
            )}
          </div>

          <div className="panel-footer">
            {simulation.status === 'completed' ? (
              <div style={{
                padding: '1rem',
                background: '#e8f5e9',
                border: '2px solid #4caf50',
                borderRadius: '8px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🏁</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#2e7d32', marginBottom: '0.25rem' }}>
                  Simulation Complete
                </div>
                <div style={{ fontSize: '0.85rem', color: '#558b2f' }}>
                  {latestRound?.continuation_reasoning || 'The simulation has reached its natural conclusion.'}
                </div>
              </div>
            ) : (
              <button
                className="next-button"
                onClick={handleNextRound}
                disabled={processing}
              >
                {processing ? 'Processing...' : 'Next Round'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Actor Detail Modal */}
      {selectedActor && (
        <div className="modal-overlay" onClick={() => setSelectedActor(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedActor(null)}>
              ×
            </button>
            
            <h2>{selectedActor.identifier}</h2>
            
            <div className="actor-details">
              <div className="detail-section">
                <h4>Role</h4>
                <p>{selectedActor.role_in_simulation}</p>
              </div>

              {(() => {
                const roundKey = latestRound?.round_number !== undefined ? String(latestRound.round_number) : null
                
                console.log('🎭 Modal Debug:', {
                  selectedActorId: selectedActor.actor_id,
                  selectedActorIdentifier: selectedActor.identifier,
                  latestRoundNumber: latestRound?.round_number,
                  roundKey,
                  availableRoundKeys: simulation.actor_states ? Object.keys(simulation.actor_states) : [],
                  actorIdsInRound: roundKey && simulation.actor_states?.[roundKey] 
                    ? Object.keys(simulation.actor_states[roundKey]) 
                    : []
                })
                
                // Get current action from latest round
                const latestActionResult = latestRound?.action_results?.find(
                  r => r.actor_id === selectedActor.actor_id
                )
                
                // Get actor's state from actor_states (round number is stored as string key)
                const actorState = (roundKey && selectedActor.actor_id)
                  ? simulation.actor_states?.[roundKey]?.[selectedActor.actor_id]
                  : undefined
                
                console.log('🔍 Actor state lookup:', { 
                  roundKey, 
                  actorId: selectedActor.actor_id,
                  foundActorState: !!actorState,
                  actorStateKeys: actorState ? Object.keys(actorState) : 'not found'
                })
                
                const latestAction = actorState?.my_actions?.[actorState.my_actions.length - 1]
                
                if (latestActionResult || actorState) {
                  return (
                    <>
                      {latestActionResult && (
                        <div className="detail-section">
                          <h4>Latest Action ({simulation.time_unit} {latestRound?.round_number !== undefined ? latestRound.round_number : 0})</h4>
                          <p><strong>{latestActionResult.action}</strong></p>
                          <p style={{ fontSize: '0.8rem', color: '#999', marginTop: '0.25rem' }}>
                            {latestActionResult.outcome}
                          </p>
                        </div>
                      )}
                      
                      {latestAction?.reasoning && (
                        <div className="detail-section">
                          <h4>Reasoning (Private)</h4>
                          <p style={{ fontSize: '0.85rem', fontStyle: 'italic', color: '#555' }}>
                            {latestAction.reasoning}
                          </p>
                        </div>
                      )}
                      
                      {actorState && (
                        <div className="detail-section">
                          <h4>Current State</h4>
                          <pre style={{ 
                            maxHeight: '300px', 
                            overflowY: 'auto', 
                            fontSize: '0.75rem',
                            padding: '0.75rem',
                            background: '#f5f5f5',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                            margin: 0,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            color: '#333'
                          }}>
                            {JSON.stringify({
                              observations: actorState.observations,
                              available_actions: actorState.available_actions,
                              disabled_actions: actorState.disabled_actions,
                              resources: actorState.resources,
                              constraints: actorState.constraints,
                              direct_impacts: actorState.direct_impacts,
                              indirect_impacts: actorState.indirect_impacts,
                              messages_received: actorState.messages_received
                            }, null, 2)}
                          </pre>
                        </div>
                      )}
                    </>
                  )
                }
                return null
              })()}

              <button
                className="download-button"
                onClick={() => {
                  const json = JSON.stringify(selectedActor, null, 2)
                  const blob = new Blob([json], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `${selectedActor.identifier}.json`
                  a.click()
                }}
              >
                Download Full Profile (JSON)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
