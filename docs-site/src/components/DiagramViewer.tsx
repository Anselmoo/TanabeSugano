import { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { loadCSV, DiagramData } from '../utils/dataLoader'

interface DiagramViewerProps {
  config: string
}

const DiagramViewer = ({ config }: DiagramViewerProps) => {
  const [diagramType, setDiagramType] = useState<'TS' | 'DD'>('TS')
  const [data, setData] = useState<DiagramData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [availableFiles, setAvailableFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<string>('')

  useEffect(() => {
    const discoverFiles = async () => {
      try {
        const basePath = `/TanabeSugano/ts-diagrams/${config}`
        const response = await fetch(basePath + '/')

        if (response.ok) {
          const text = await response.text()
          const parser = new DOMParser()
          const doc = parser.parseFromString(text, 'text/html')
          const links = Array.from(doc.querySelectorAll('a'))

          const csvFiles = links
            .map(link => link.getAttribute('href'))
            .filter(href => href?.endsWith('.csv'))
            .filter(Boolean) as string[]

          setAvailableFiles(csvFiles)

          // Auto-select first file of current diagram type
          const typeFiles = csvFiles.filter(f =>
            diagramType === 'TS' ? f.includes('TS_Cut') : f.includes('DD-energies')
          )

          if (typeFiles.length > 0) {
            setSelectedFile(typeFiles[0])
          }
        }
      } catch (err) {
        console.error('Error discovering files:', err)
      }
    }

    discoverFiles()
  }, [config, diagramType])

  useEffect(() => {
    if (!selectedFile) return

    const loadData = async () => {
      setLoading(true)
      setError(null)

      try {
        const basePath = `/TanabeSugano/ts-diagrams/${config}`
        const filePath = `${basePath}/${selectedFile}`
        const csvData = await loadCSV(filePath)
        setData(csvData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load diagram data')
        setData(null)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [config, selectedFile])

  const handleDiagramTypeChange = (type: 'TS' | 'DD') => {
    setDiagramType(type)
    setSelectedFile('')
    setData(null)
  }

  const getXAxisTitle = () => {
    return diagramType === 'TS' ? 'Δ/B (10Dq/B)' : '10Dq (cm⁻¹)'
  }

  const getYAxisTitle = () => {
    return 'E/B (Energy/B)' + (diagramType === 'DD' ? ' or Energy (cm⁻¹)' : '')
  }

  const getTitle = () => {
    return diagramType === 'TS'
      ? `Tanabe-Sugano Diagram (${config.toUpperCase()})`
      : `DD Energy Diagram (${config.toUpperCase()})`
  }

  return (
    <div>
      <div className="controls">
        <h3 style={{ marginBottom: '1rem' }}>Diagram Type</h3>
        <div className="button-group">
          <button
            className={diagramType === 'TS' ? 'active' : ''}
            onClick={() => handleDiagramTypeChange('TS')}
          >
            Tanabe-Sugano
          </button>
          <button
            className={diagramType === 'DD' ? 'active' : ''}
            onClick={() => handleDiagramTypeChange('DD')}
          >
            DD Energy
          </button>
        </div>

        {availableFiles.length > 0 && (
          <div style={{ marginTop: '1rem', textAlign: 'center' }}>
            <label htmlFor="file-select" style={{ marginRight: '0.5rem' }}>
              Select Data File:
            </label>
            <select
              id="file-select"
              value={selectedFile}
              onChange={(e) => setSelectedFile(e.target.value)}
            >
              <option value="">-- Select a file --</option>
              {availableFiles
                .filter(f => diagramType === 'TS' ? f.includes('TS_Cut') : f.includes('DD-energies'))
                .map(file => (
                  <option key={file} value={file}>
                    {file}
                  </option>
                ))}
            </select>
          </div>
        )}
      </div>

      {loading && <div className="loading">Loading diagram...</div>}

      {error && (
        <div className="error">
          <strong>Error:</strong> {error}
          <div className="diagram-info">
            Make sure CSV files are available in ts-diagrams/{config}/ directory.
          </div>
        </div>
      )}

      {!loading && !error && data && (
        <div className="chart-container">
          <Plot
            data={data.traces.map(trace => ({
              x: data.xValues,
              y: trace.yValues,
              type: 'scatter',
              mode: 'lines',
              name: trace.name,
              line: { width: 2 }
            }))}
            layout={{
              title: getTitle(),
              xaxis: {
                title: getXAxisTitle(),
                gridcolor: '#e0e0e0'
              },
              yaxis: {
                title: getYAxisTitle(),
                gridcolor: '#e0e0e0'
              },
              autosize: true,
              hovermode: 'closest',
              showlegend: true,
              legend: {
                orientation: 'v',
                x: 1.02,
                y: 1
              }
            }}
            config={{
              responsive: true,
              displayModeBar: true,
              displaylogo: false,
              toImageButtonOptions: {
                format: 'png',
                filename: `${diagramType}_${config}`,
                height: 800,
                width: 1200,
                scale: 2
              }
            }}
            style={{ width: '100%', height: '600px' }}
          />

          <div className="diagram-info">
            <strong>Info:</strong> Displaying {data.traces.length} energy states
            with {data.xValues.length} data points.
            Use mouse to zoom, pan, and hover for values.
            Click camera icon to download image.
          </div>
        </div>
      )}
    </div>
  )
}

export default DiagramViewer
