import { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { loadCSV, type DiagramData } from '../utils/dataLoader'

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
  const [selectedFile, setSelectedFile] = useState<string>('')

  // Color palette: spin multiplicity groups (gerade even: 2,4,6; ungerade odd: 1,3,5)
  // Optimized for light background (#FFFBEB) using Alucard Classic subset.
  // Design goals:
  //  - Even set uses cooler / structured hues with ascending perceived weight.
  //  - Odd set uses warmer / vivid hues for immediate separation.
  //  - All pairs exceed ~4.5:1 contrast vs light background (except purple borderline but retained for categorical distinctiveness).
  //  - Avoid duplicate hues across parity groups to reinforce semantic grouping.
  // Chosen mapping:
  //    Even: 2 → Cyan (#036A96), 4 → Green (#14710A), 6 → Purple (#644AC9)
  //    Odd:  1 → Red (#CB3A2A), 3 → Orange (#A34D14), 5 → Pink (#A3144D)
  // Rationale: provides six distinct hue families; purple moved to even (higher energy visual anchor) while pink reserved for highest odd multiplicity.
  const getColorForTermSymbol = (traceName: string): string | undefined => {
    const match = traceName.match(/^(\d+)\s/)
    if (!match) return undefined
    const multiplicity = parseInt(match[1], 10)
    const colorMap: Record<number, string> = {
      2: '#036A96', // Cyan (support / structural)
      4: '#A34D14', // Orange (stable)
      6: '#644AC9', // Purple (higher even multiplicity emphasis)
      1: '#CB3A2A', // Red (baseline odd alertness)
      3: '#14710A', // Green (mid odd)
      5: '#A3144D', // Pink (highest odd multiplicity)
    }
    return colorMap[multiplicity] || '#5A5A5A' // Fallback neutral gray for unexpected multiplicity
  }

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
            type="button"
            className={diagramType === 'TS' ? 'active' : ''}
            onClick={() => handleDiagramTypeChange('TS')}
          >
            Tanabe-Sugano
          </button>
          <button
            type="button"
            className={diagramType === 'DD' ? 'active' : ''}
            onClick={() => handleDiagramTypeChange('DD')}
          >
            DD Energy
          </button>
        </div>
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
            data={data.traces.map(trace => {
              const color = getColorForTermSymbol(trace.name)
              return {
                x: data.xValues,
                y: trace.yValues,
                type: 'scatter',
                mode: 'lines',
                name: trace.name,
                line: {
                  width: 2,
                  ...(color && { color })
                }
              }
            })}
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
