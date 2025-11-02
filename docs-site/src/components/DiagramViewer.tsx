import { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { loadCSV, DiagramData } from '../utils/dataLoader'

interface DiagramViewerProps {
  config: string
}

interface ManifestFile {
  name: string
  path: string
  type: string
}

interface Manifest {
  [key: string]: ManifestFile[]
}

const DiagramViewer = ({ config }: DiagramViewerProps) => {
  const [diagramType, setDiagramType] = useState<'TS' | 'DD'>('TS')
  const [data, setData] = useState<DiagramData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [availableFiles, setAvailableFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<string>('')

  useEffect(() => {
    const loadManifest = async () => {
      try {
        const response = await fetch('/TanabeSugano/ts-diagrams/manifest.json')
        
        if (response.ok) {
          const manifest: Manifest = await response.json()
          const configFiles: ManifestFile[] = manifest[config] || []
          
          // Filter files by diagram type
          const filteredFiles = configFiles.filter((file: ManifestFile) => 
            diagramType === 'TS' 
              ? (file.name.includes('TS_Cut') || file.name.includes('TS-diagram'))
              : file.name.includes('DD-energies')
          )
          
          // Sort to prefer full diagrams over cut diagrams
          filteredFiles.sort((a: ManifestFile, b: ManifestFile) => {
            // Prefer TS-diagram over TS_Cut for TS type
            if (diagramType === 'TS') {
              if (a.name.includes('TS-diagram') && !b.name.includes('TS-diagram')) return -1
              if (!a.name.includes('TS-diagram') && b.name.includes('TS-diagram')) return 1
            }
            return a.name.localeCompare(b.name)
          })
          
          setAvailableFiles(filteredFiles.map((f: ManifestFile) => f.name))

          // Auto-select first file of current diagram type (now sorted to prefer full diagrams)
          if (filteredFiles.length > 0) {
            setSelectedFile(filteredFiles[0].name)
          } else {
            setSelectedFile('')
            setData(null)
          }
        }
      } catch (err) {
        console.error('Error loading manifest:', err)
        setAvailableFiles([])
      }
    }

    loadManifest()
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
              title: {
                text: getTitle()
              },
              xaxis: {
                title: {
                  text: getXAxisTitle()
                },
                gridcolor: '#e0e0e0'
              },
              yaxis: {
                title: {
                  text: getYAxisTitle()
                },
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
