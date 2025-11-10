import { useState } from 'react'
import DiagramViewer from './components/DiagramViewer'
import './App.css'

function App() {
  const [selectedConfig, setSelectedConfig] = useState<string>('d3')

  const configs = ['d2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']

  return (
    <>
      <h1>Tanabe-Sugano Diagrams</h1>
      <div className="controls">
        <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>
          Select Electron Configuration
        </h2>
        <div className="button-group">
          {configs.map(config => (
            <button
              key={config}
              className={selectedConfig === config ? 'active' : ''}
              onClick={() => setSelectedConfig(config)}
            >
              {config.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <DiagramViewer config={selectedConfig} />
    </>
  )
}

export default App
