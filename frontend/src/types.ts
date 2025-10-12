export interface Actor {
  actor_id?: string
  identifier: string
  research_query: string
  granularity: string
  scale_notes: string
  role_in_simulation: string
  key_interactions: string[]
  memory?: string | any
  intrinsic_characteristics?: string | any
  predispositions?: string | any
  enriched?: boolean
}

export interface Simulation {
  simulation_id: string
  question: string
  time_unit: string
  simulation_duration: number
  status: 'created' | 'enriching' | 'enriched' | 'running' | 'completed'
  actors: Actor[]
  current_round: number
  current_time?: number
  actor_states?: any
}

export interface Round {
  round_number: number
  world_state_summary: string
  key_changes: string[]
  emergent_developments: string[]
  action_results: ActionResult[]
  continue_simulation: boolean
  continuation_reasoning: string
  timestamp: string
}

export interface ActionResult {
  actor_id: string
  action: string
  success_threshold: number
  random_seed: number
  outcome: string
  outcome_quality: string
  explanation: string
}

export interface Message {
  from_actor_id: string
  to_actor_id: string
  content: string
}

