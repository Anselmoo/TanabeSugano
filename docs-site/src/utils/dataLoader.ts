import Papa from 'papaparse'

export interface DiagramData {
  xValues: number[]
  traces: {
    name: string
    yValues: number[]
  }[]
}

export interface DiagramFile {
  name: string
  type: 'TS' | 'DD'
  path: string
}

export const loadCSV = async (path: string): Promise<DiagramData> => {
  const response = await fetch(path)
  const csvText = await response.text()

  return new Promise((resolve, reject) => {
    Papa.parse(csvText, {
      header: true,
      dynamicTyping: true,
      complete: (results) => {
        const data = results.data as any[]

        if (data.length === 0) {
          reject(new Error('No data found in CSV'))
          return
        }

        const headers = Object.keys(data[0])
        const xKey = headers[0] // First column is X-axis (10Dq or 10Dq/B)

        const xValues = data.map(row => row[xKey]).filter(v => v != null)

        const traces = headers.slice(1).map(header => ({
          name: header.replace(/_/g, ' '),
          yValues: data.map(row => row[header]).filter(v => v != null)
        }))

        resolve({ xValues, traces })
      },
      error: (error) => {
        reject(error)
      }
    })
  })
}

export const findDiagramFiles = async (config: string): Promise<DiagramFile[]> => {
  // In a real implementation, we'd scan the directory
  // For now, we'll construct expected file names
  const basePath = `/TanabeSugano/ts-diagrams/${config}`

  try {
    // Try to find available CSV files
    const files: DiagramFile[] = []

    // Look for pattern: DD-energies_*.csv and TS_Cut_*.csv
    const response = await fetch(`${basePath}/`)

    if (response.ok) {
      const html = await response.text()
      const parser = new DOMParser()
      const doc = parser.parseFromString(html, 'text/html')
      const links = Array.from(doc.querySelectorAll('a'))

      links.forEach(link => {
        const href = link.getAttribute('href')
        if (href?.endsWith('.csv')) {
          if (href.startsWith('DD-energies')) {
            files.push({
              name: 'DD Energy Diagram',
              type: 'DD',
              path: `${basePath}/${href}`
            })
          } else if (href.startsWith('TS_Cut') || href.startsWith('TS-diagram')) {
            files.push({
              name: 'Tanabe-Sugano Diagram',
              type: 'TS',
              path: `${basePath}/${href}`
            })
          }
        }
      })
    }

    // Fallback: try common patterns
    if (files.length === 0) {
      const commonFiles = [
        { name: 'DD Energy Diagram', type: 'DD' as const, suffix: 'DD-energies' },
        { name: 'Tanabe-Sugano Diagram', type: 'TS' as const, suffix: 'TS_Cut' }
      ]

      for (const file of commonFiles) {
        try {
          const testPath = `${basePath}/${file.suffix}_${config}_*.csv`
          files.push({
            name: file.name,
            type: file.type,
            path: testPath
          })
        } catch (e) {
          // Skip if file doesn't exist
        }
      }
    }

    return files
  } catch (error) {
    console.error('Error finding diagram files:', error)
    return []
  }
}

export const getAvailableCSVFiles = (config: string): string[] => {
  // Return expected CSV file patterns for the config
  const basePath = `/TanabeSugano/ts-diagrams/${config}`
  return [
    `${basePath}/DD-energies_${config}_10Dq_40000_B_*_C_*.csv`,
    `${basePath}/TS_Cut_${config}_10Dq_*_B_*_C_*.csv`
  ]
}
