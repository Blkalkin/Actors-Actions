export interface Actor {
  identifier: string
  research_query: string
  granularity: string
  scale_notes: string
  role_in_simulation: string
  key_interactions: string[]
  memory?: string
  intrinsic_characteristics?: string
  predispositions?: string
  enriched?: boolean
}

export interface Simulation {
  simulation_id: string
  question: string
  time_unit: string
  simulation_duration: number
  status: 'created' | 'enriching' | 'enriched' | 'running' | 'completed'
  actors: Actor[]
  current_time?: number
}

export interface TranscriptEntry {
  time_unit: number
  timestamp: string
  actions: any[]
  world_update: any
}

