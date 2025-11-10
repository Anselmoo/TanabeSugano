# Tanabe-Sugano Diagram Viewer

An interactive web application for visualizing Tanabe-Sugano diagrams and DD energy diagrams for d2-d8 electron configurations.

## Features

- **Interactive Visualization**: Powered by Plotly.js for smooth, interactive charts
- **Multiple Configurations**: Support for d2, d3, d4, d5, d6, d7, and d8 electron configurations
- **Dual Diagram Types**:
  - Tanabe-Sugano diagrams (Energy/B vs Δ/B)
  - DD Energy diagrams (Energy vs 10Dq)
- **CSV Data Loading**: Dynamically loads diagram data from CSV files
- **Export Capability**: Download diagrams as PNG images
- **Responsive Design**: Works on desktop and mobile devices

## Technology Stack

- **Vite**: Fast build tool and dev server
- **React 19**: UI framework
- **TypeScript**: Type-safe development
- **Plotly.js**: Scientific charting library
- **PapaParse**: CSV parsing
- **GitHub Pages**: Static site hosting

## Development

### Prerequisites

- Node.js 20 or higher
- npm

### Setup

```bash
cd docs-site
npm install
```

### Development Server

```bash
npm run dev
```

Visit `http://localhost:5173/TanabeSugano/` in your browser.

### Build

```bash
npm run build
```

Output will be in `../docs/` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
docs-site/
├── public/
│   └── ts-diagrams/     # CSV data files (d2-d8)
├── src/
│   ├── components/
│   │   └── DiagramViewer.tsx    # Main diagram component
│   ├── utils/
│   │   └── dataLoader.ts        # CSV loading utilities
│   ├── App.tsx                   # Main app component
│   ├── main.tsx                  # App entry point
│   └── index.css                 # Global styles
├── index.html
├── vite.config.ts
└── package.json
```

## Data Format

The application expects CSV files in the following format:

- **Tanabe-Sugano diagrams**: `TS_Cut_<config>_*.csv`
  - First column: Δ/B (10Dq/B)
  - Subsequent columns: Energy states (E/B)

- **DD Energy diagrams**: `DD-energies_<config>_*.csv`
  - First column: 10Dq (cm⁻¹)
  - Subsequent columns: Energy states

## Deployment

The site is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the master branch.

The workflow:
1. Checks out the repository
2. Installs Node.js dependencies
3. Copies CSV data to public directory
4. Builds the Vite application
5. Uploads and deploys to GitHub Pages

## Usage

1. Select an electron configuration (d2-d8) using the buttons at the top
2. Choose between Tanabe-Sugano or DD Energy diagram type
3. Select a specific CSV file from the dropdown
4. Interact with the plot:
   - Zoom: Click and drag
   - Pan: Shift + click and drag
   - Reset: Double-click
   - Export: Click camera icon

## License

See main project LICENSE file.
