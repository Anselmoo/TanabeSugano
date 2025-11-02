#!/usr/bin/env node
/**
 * Script to generate an index of all Tanabe-Sugano diagrams
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TS_DIAGRAMS_DIR = path.join(__dirname, '..', 'ts-diagrams');
const OUTPUT_FILE = path.join(__dirname, 'src', 'diagrams-index.json');

// Regular expression pattern for parsing diagram filenames
// Expected format: TS-diagram_d{N}_10Dq_{value}_B_{value}_C_{value}.html
const DIAGRAM_FILENAME_PATTERN = /d(\d+)_10Dq_(\d+)_B_([0-9.]+)_C_([0-9.]+)/;

// Valid electron configuration directory pattern
const ELECTRON_CONFIG_PATTERN = /^d(\d+)$/;

function generateIndex() {
  const diagrams = [];
  
  // Verify ts-diagrams directory exists
  if (!fs.existsSync(TS_DIAGRAMS_DIR)) {
    console.error(`Error: Directory ${TS_DIAGRAMS_DIR} does not exist`);
    process.exit(1);
  }
  
  // Read all d* directories (d2, d3, ..., d8)
  const electronConfigs = fs.readdirSync(TS_DIAGRAMS_DIR)
    .filter(file => {
      const fullPath = path.join(TS_DIAGRAMS_DIR, file);
      return fs.statSync(fullPath).isDirectory() && ELECTRON_CONFIG_PATTERN.test(file);
    })
    .sort();

  for (const config of electronConfigs) {
    const configPath = path.join(TS_DIAGRAMS_DIR, config);
    const files = fs.readdirSync(configPath);
    
    // Find TS-diagram and DD-energies HTML files
    const tsDiagram = files.find(f => f.startsWith('TS-diagram_') && f.endsWith('.html'));
    const ddEnergies = files.find(f => f.startsWith('DD-energies_') && f.endsWith('.html'));
    const tsCsv = files.find(f => f.startsWith('TS-diagram_') && f.endsWith('.csv'));
    const ddCsv = files.find(f => f.startsWith('DD-energies_') && f.endsWith('.csv'));
    
    if (tsDiagram || ddEnergies) {
      // Parse parameters from filename
      const match = tsDiagram ? tsDiagram.match(DIAGRAM_FILENAME_PATTERN) : null;
      
      // Extract electron configuration number with validation
      const configMatch = config.match(ELECTRON_CONFIG_PATTERN);
      const dNumberFromConfig = configMatch ? parseInt(configMatch[1]) : null;
      
      if (!dNumberFromConfig) {
        console.warn(`Warning: Skipping invalid directory name: ${config}`);
        continue;
      }
      
      // Parse parameters from filename or use defaults
      const dNumber = match ? parseInt(match[1]) : dNumberFromConfig;
      const tenDq = match ? parseInt(match[2]) : null;
      const racahB = match ? parseFloat(match[3]) : null;
      const racahC = match ? parseFloat(match[4]) : null;
      
      if (!match && tsDiagram) {
        console.warn(`Warning: Could not parse parameters from filename: ${tsDiagram}`);
      }
      
      diagrams.push({
        electronConfig: config,
        dNumber,
        tenDq,
        racahB,
        racahC,
        files: {
          tsDiagram: tsDiagram ? `ts-diagrams/${config}/${tsDiagram}` : null,
          ddEnergies: ddEnergies ? `ts-diagrams/${config}/${ddEnergies}` : null,
          tsCsv: tsCsv ? `ts-diagrams/${config}/${tsCsv}` : null,
          ddCsv: ddCsv ? `ts-diagrams/${config}/${ddCsv}` : null,
        }
      });
    }
  }

  // Ensure output directory exists
  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Write index to file
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(diagrams, null, 2));
  console.log(`Generated index with ${diagrams.length} diagrams at ${OUTPUT_FILE}`);
}

generateIndex();
