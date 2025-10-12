import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './QuestionInputPage.css'

export default function QuestionInputPage() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!question.trim()) return

    console.log('🚀 Creating simulation...', question)
    setLoading(true)
    
    try {
      const result = await api.createSimulation(question)
      console.log('✅ Simulation created:', result.simulation_id)
      // Redirect to questions list
      navigate('/questions')
    } catch (err) {
      console.error('❌ Failed to create simulation:', err)
      alert('Failed to create simulation. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="question-input-page">
      <button 
        className="nav-button"
        onClick={() => navigate('/questions')}
      >
        Questions
      </button>

      <div className="question-input-container">
        <h1 className="title">Question</h1>
        
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            className="question-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What social situation do you want to simulate?"
            disabled={loading}
            autoFocus
          />
          
          <button 
            type="submit" 
            className={`submit-button ${loading ? 'loading' : ''}`}
            disabled={loading || !question.trim()}
          >
            {loading ? '◯' : '→'}
          </button>
        </form>
      </div>
    </div>
  )
}

