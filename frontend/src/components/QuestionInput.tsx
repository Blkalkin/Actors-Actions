import { useState } from 'react'
import './QuestionInput.css'

interface QuestionInputProps {
  onSubmit: (question: string) => void
  loading?: boolean
}

export function QuestionInput({ onSubmit, loading }: QuestionInputProps) {
  const [question, setQuestion] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (question.trim()) {
      onSubmit(question.trim())
    }
  }

  const exampleQuestions = [
    "How will a city respond to a major tech company announcing 10,000 layoffs over the next 6 months?",
    "What happens when a new AI regulation is proposed that requires companies to disclose training data sources?",
    "How will the gig economy evolve if a major platform introduces worker protections?",
  ]

  return (
    <div className="question-input">
      <h2>What would you like to simulate?</h2>
      <p className="subtitle">Enter a social question or situation to explore</p>

      <form onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Enter your question here..."
          rows={4}
          disabled={loading}
        />

        <button 
          type="submit" 
          className="btn btn-primary btn-large"
          disabled={!question.trim() || loading}
        >
          {loading ? '🤖 Generating Actors...' : '🚀 Create Simulation'}
        </button>
      </form>

      <div className="examples">
        <p className="examples-title">Example questions:</p>
        {exampleQuestions.map((ex, i) => (
          <button
            key={i}
            className="example-button"
            onClick={() => setQuestion(ex)}
            disabled={loading}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}

