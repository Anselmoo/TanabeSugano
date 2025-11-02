# Tanabe-Sugano Diagrams Viewer

This is a React-based web application for viewing and exploring Tanabe-Sugano diagrams for d²-d⁸ transition metal ions.

## Features

- Interactive visualization of Tanabe-Sugano diagrams
- Energy-Correlation (DD) diagrams
- Download CSV and HTML files for each diagram
- Responsive design for mobile and desktop
- Hosted on GitHub Pages

## Development

### Prerequisites

- Node.js 20 or higher
- npm

### Setup

```bash
npm install
```

### Development Server

```bash
npm run dev
```

This will start a local development server at `http://localhost:5173`.

### Build

```bash
npm run build
```

This will:
1. Generate an index of all available diagrams
2. Build the production-ready site in the `../docs` folder

### Generate Diagram Index

```bash
npm run generate-index
```

This script scans the `../ts-diagrams` directory and creates an index of all available Tanabe-Sugano diagrams.

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the `master` branch via GitHub Actions.

## Configuration

- `vite.config.js` - Vite configuration, including the base path for GitHub Pages
- `generate-index.js` - Script to generate the diagram index

## About

The diagrams are based on the original studies by Yukito Tanabe and Satoru Sugano (1954-1956) for d²-d⁸ transition metal ions.
