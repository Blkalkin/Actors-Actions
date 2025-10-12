import { useState } from 'react'
import type { Actor } from '../types'
import './ActorVisualization.css'

interface ActorVisualizationProps {
  actors: Actor[]
}

export function ActorVisualization({ actors }: ActorVisualizationProps) {
  const [selectedActor, setSelectedActor] = useState<Actor | null>(null)

  const getActorColor = (granularity: string) => {
    const colors: Record<string, string> = {
      Individual: '#FF6B6B',
      Group: '#4ECDC4',
      Organization: '#45B7D1',
      Sector: '#96CEB4',
      Geographic: '#FECA57',
      Other: '#A8A8A8',
    }
    return colors[granularity] || colors.Other
  }

  return (
    <div className="actor-visualization">
      <h3>Actors ({actors.length})</h3>
      
      <div className="actors-grid">
        {actors.map((actor) => (
          <div
            key={actor.identifier}
            className={`actor-card ${selectedActor?.identifier === actor.identifier ? 'selected' : ''}`}
            style={{ borderColor: getActorColor(actor.granularity) }}
            onClick={() => setSelectedActor(actor)}
          >
            <div 
              className="actor-icon"
              style={{ background: getActorColor(actor.granularity) }}
            >
              {actor.identifier.charAt(0)}
            </div>
            <div className="actor-info">
              <h4>{actor.identifier.replace(/_/g, ' ')}</h4>
              <p className="actor-granularity">{actor.granularity}</p>
              {actor.enriched && <span className="enriched-badge">✨ Enriched</span>}
            </div>
          </div>
        ))}
      </div>

      {selectedActor && (
        <div className="actor-details">
          <div className="actor-details-header">
            <h3>{selectedActor.identifier.replace(/_/g, ' ')}</h3>
            <button onClick={() => setSelectedActor(null)}>✕</button>
          </div>

          <div className="actor-details-content">
            <div className="detail-section">
              <h4>Role</h4>
              <p>{selectedActor.role_in_simulation}</p>
            </div>

            <div className="detail-section">
              <h4>Scale</h4>
              <p>{selectedActor.scale_notes}</p>
            </div>

            <div className="detail-section">
              <h4>Interacts With</h4>
              <div className="interactions">
                {selectedActor.key_interactions.map((id) => (
                  <span key={id} className="interaction-tag">
                    {id.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>

            {selectedActor.enriched && (
              <>
                <div className="detail-section">
                  <h4>Memory</h4>
                  <p className="detail-text">{selectedActor.memory?.substring(0, 300)}...</p>
                </div>

                <div className="detail-section">
                  <h4>Characteristics</h4>
                  <p className="detail-text">{selectedActor.intrinsic_characteristics?.substring(0, 300)}...</p>
                </div>

                <div className="detail-section">
                  <h4>Predispositions</h4>
                  <p className="detail-text">{selectedActor.predispositions?.substring(0, 300)}...</p>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

