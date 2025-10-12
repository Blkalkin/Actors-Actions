import axios from 'axios'
import type { Simulation } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const api = {
  async createSimulation(question: string): Promise<Simulation> {
    const response = await client.post('/api/simulations/create', { question })
    return response.data
  },

  async getSimulation(simulationId: string): Promise<Simulation> {
    const response = await client.get(`/api/simulations/${simulationId}`)
    return response.data
  },

  async enrichSimulation(simulationId: string): Promise<Simulation> {
    const response = await client.post(`/api/simulations/${simulationId}/enrich`)
    return response.data
  },

  async listSimulations(): Promise<{ simulations: Simulation[], count: number }> {
    const response = await client.get('/api/simulations')
    return response.data
  },

  async getRounds(simulationId: string): Promise<any[]> {
    const response = await client.get(`/api/simulations/${simulationId}/rounds`)
    return response.data.rounds || []
  },

  async processRound(simulationId: string): Promise<any> {
    const response = await client.post(`/api/simulations/${simulationId}/process-round`)
    return response.data
  },
}

