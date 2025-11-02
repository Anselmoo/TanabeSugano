import { useState } from 'react'
import './App.css'
import diagramsData from './diagrams-index.json'

function App() {
  const [selectedDiagram, setSelectedDiagram] = useState(null);
  const [viewType, setViewType] = useState('ts'); // 'ts' or 'dd'

  const handleDiagramClick = (diagram) => {
    setSelectedDiagram(diagram);
    setViewType('ts');
  };

  return (
    <div className="App">
      <header className="header">
        <h1>Tanabe-Sugano Diagrams</h1>
        <p className="subtitle">
          Interactive visualization of d<sup>2</sup>-d<sup>8</sup> transition metal ion diagrams
        </p>
      </header>

      <main className="main-content">
        <aside className="sidebar">
          <h2>Electron Configurations</h2>
          <div className="diagram-list">
            {diagramsData.map((diagram) => (
              <button
                key={diagram.electronConfig}
                className={`diagram-button ${selectedDiagram?.electronConfig === diagram.electronConfig ? 'active' : ''}`}
                onClick={() => handleDiagramClick(diagram)}
              >
                <span className="config-name">d<sup>{diagram.dNumber}</sup></span>
                <div className="params">
                  <small>10Dq: {diagram.tenDq} cm<sup>-1</sup></small>
                  <small>B: {diagram.racahB} cm<sup>-1</sup></small>
                  <small>C: {diagram.racahC} cm<sup>-1</sup></small>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="content">
          {!selectedDiagram ? (
            <div className="welcome">
              <h2>Welcome to the Tanabe-Sugano Diagram Viewer</h2>
              <p>
                Select an electron configuration from the sidebar to view the corresponding 
                Tanabe-Sugano and Energy-Correlation diagrams.
              </p>
              <div className="info">
                <h3>About</h3>
                <p>
                  These diagrams are based on the original studies by Yukito Tanabe and Satoru Sugano 
                  for d<sup>2</sup>-d<sup>8</sup> transition metal ions.
                </p>
                <ul>
                  <li><strong>TS Diagram:</strong> Tanabe-Sugano diagram showing energy levels vs. crystal field splitting</li>
                  <li><strong>DD Energies:</strong> Energy-Correlation diagram showing d-d transitions</li>
                </ul>
              </div>
            </div>
          ) : (
            <>
              <div className="diagram-header">
                <h2>
                  d<sup>{selectedDiagram.dNumber}</sup> Configuration
                </h2>
                <div className="view-controls">
                  <button
                    className={`view-button ${viewType === 'ts' ? 'active' : ''}`}
                    onClick={() => setViewType('ts')}
                  >
                    TS Diagram
                  </button>
                  <button
                    className={`view-button ${viewType === 'dd' ? 'active' : ''}`}
                    onClick={() => setViewType('dd')}
                  >
                    DD Energies
                  </button>
                </div>
              </div>

              <div className="diagram-params">
                <span>10Dq: {selectedDiagram.tenDq} cm<sup>-1</sup></span>
                <span>Racah B: {selectedDiagram.racahB} cm<sup>-1</sup></span>
                <span>Racah C: {selectedDiagram.racahC} cm<sup>-1</sup></span>
              </div>

              <div className="iframe-container">
                <iframe
                  src={`../${viewType === 'ts' ? selectedDiagram.files.tsDiagram : selectedDiagram.files.ddEnergies}`}
                  title={`${viewType === 'ts' ? 'Tanabe-Sugano' : 'DD Energies'} Diagram for d${selectedDiagram.dNumber}`}
                  className="diagram-iframe"
                />
              </div>

              <div className="download-links">
                <h3>Download Data</h3>
                <div className="links">
                  {selectedDiagram.files.tsCsv && (
                    <a href={`../${selectedDiagram.files.tsCsv}`} download>
                      📊 TS Diagram CSV
                    </a>
                  )}
                  {selectedDiagram.files.ddCsv && (
                    <a href={`../${selectedDiagram.files.ddCsv}`} download>
                      📊 DD Energies CSV
                    </a>
                  )}
                  {selectedDiagram.files.tsDiagram && (
                    <a href={`../${selectedDiagram.files.tsDiagram}`} download>
                      📄 TS Diagram HTML
                    </a>
                  )}
                  {selectedDiagram.files.ddEnergies && (
                    <a href={`../${selectedDiagram.files.ddEnergies}`} download>
                      📄 DD Energies HTML
                    </a>
                  )}
                </div>
              </div>
            </>
          )}
        </section>
      </main>

      <footer className="footer">
        <p>
          Based on the work of Yukito Tanabe and Satoru Sugano (1954-1956)
        </p>
        <p>
          <a href="https://github.com/Anselmoo/TanabeSugano" target="_blank" rel="noopener noreferrer">
            View on GitHub
          </a>
        </p>
      </footer>
    </div>
  )
}

export default App
