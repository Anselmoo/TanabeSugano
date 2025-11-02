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

function generateIndex() {
  const diagrams = [];
  
  // Read all d* directories (d2, d3, ..., d8)
  const electronConfigs = fs.readdirSync(TS_DIAGRAMS_DIR)
    .filter(file => {
      const fullPath = path.join(TS_DIAGRAMS_DIR, file);
      return fs.statSync(fullPath).isDirectory() && file.match(/^d\d+$/);
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
      // e.g., TS-diagram_d5_10Dq_40000_B_860_C_3850.html
      const match = tsDiagram ? tsDiagram.match(/d(\d+)_10Dq_(\d+)_B_([0-9.]+)_C_([0-9.]+)/) : null;
      
      diagrams.push({
        electronConfig: config,
        dNumber: match ? parseInt(match[1]) : parseInt(config.substring(1)),
        tenDq: match ? parseInt(match[2]) : null,
        racahB: match ? parseFloat(match[3]) : null,
        racahC: match ? parseFloat(match[4]) : null,
        files: {
          tsDiagram: tsDiagram ? `ts-diagrams/${config}/${tsDiagram}` : null,
          ddEnergies: ddEnergies ? `ts-diagrams/${config}/${ddEnergies}` : null,
          tsCsv: tsCsv ? `ts-diagrams/${config}/${tsCsv}` : null,
          ddCsv: ddCsv ? `ts-diagrams/${config}/${ddCsv}` : null,
        }
      });
    }
  }

  // Write index to file
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(diagrams, null, 2));
  console.log(`Generated index with ${diagrams.length} diagrams at ${OUTPUT_FILE}`);
}

generateIndex();
