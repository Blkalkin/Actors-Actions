import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import './App.css'
import QuestionInputPage from './pages/QuestionInputPage'
import QuestionsListPage from './pages/QuestionsListPage'
import SimulationPage from './pages/SimulationPage'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<QuestionInputPage />} />
        <Route path="/questions" element={<QuestionsListPage />} />
        <Route path="/simulation/:simulationId" element={<SimulationPage />} />
      </Routes>
    </Router>
  )
}

export default App
