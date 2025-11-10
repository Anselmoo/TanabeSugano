# GitHub Pages Setup for Tanabe-Sugano Diagrams

This document describes the GitHub Pages setup for hosting interactive Tanabe-Sugano diagrams.

## Overview

The GitHub Pages site provides an interactive web interface for viewing all Tanabe-Sugano and Energy-Correlation diagrams for d²-d⁸ transition metal ions. The site is built with React and Vite, and automatically deployed via GitHub Actions.

## Site URL

**Production:** https://anselmoo.github.io/TanabeSugano/

## Architecture

### Directory Structure

```
TanabeSugano/
├── docs/                    # Built site (served by GitHub Pages)
│   ├── .nojekyll           # Prevents Jekyll processing
│   ├── index.html          # Main HTML file
│   └── assets/             # Compiled JS and CSS
├── docs-site/              # React source code
│   ├── src/
│   │   ├── App.jsx         # Main React component
│   │   ├── App.css         # Styling
│   │   └── diagrams-index.json  # Generated index of diagrams
│   ├── generate-index.js   # Script to scan and index diagrams
│   ├── vite.config.js      # Vite configuration
│   └── package.json        # Dependencies and scripts
├── ts-diagrams/            # Source diagram files (HTML, CSV)
│   ├── d2/
│   ├── d3/
│   ├── ...
│   └── d8/
└── .github/
    └── workflows/
        └── deploy-pages.yml  # GitHub Actions deployment workflow
```

### Technologies

- **React 19** - UI framework
- **Vite 7** - Build tool and dev server
- **GitHub Actions** - CI/CD for automatic deployment
- **GitHub Pages** - Static site hosting

## Features

### User Features

1. **Interactive Diagram Browser**
   - Browse all electron configurations (d²-d⁸)
   - View Tanabe-Sugano (TS) diagrams
   - View Energy-Correlation (DD) diagrams

2. **Diagram Viewer**
   - Embedded interactive Plotly diagrams
   - Toggle between TS and DD views
   - Display of Racah parameters

3. **Data Download**
   - Download CSV data files
   - Download HTML diagram files

### Developer Features

1. **Automatic Index Generation**
   - Scans `ts-diagrams/` directory
   - Extracts parameters from filenames
   - Generates JSON index

2. **Automated Deployment**
   - Triggered on push to `master` branch
   - Builds and deploys automatically
   - No manual intervention required

## Development

### Prerequisites

- Node.js 20 or higher
- npm

### Local Development

1. Install dependencies:
   ```bash
   cd docs-site
   npm install
   ```

2. Generate diagram index:
   ```bash
   npm run generate-index
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

4. Visit http://localhost:5173

### Building for Production

```bash
cd docs-site
npm run build
```

This will:
1. Run `generate-index.js` to scan and index diagrams
2. Build the React app with Vite
3. Output to `../docs/` directory

## Deployment

### Automatic Deployment (Recommended)

The site is automatically deployed when changes are pushed to the `master` branch:

1. Make changes to `docs-site/` or `ts-diagrams/`
2. Commit and push to `master`
3. GitHub Actions workflow runs:
   - Checks out code
   - Installs dependencies
   - Builds the site
   - Deploys to GitHub Pages

### Manual Deployment

If needed, you can manually trigger the workflow:

1. Go to Actions tab in GitHub
2. Select "Deploy GitHub Pages" workflow
3. Click "Run workflow"
4. Select `master` branch
5. Click "Run workflow"

## Configuration

### GitHub Pages Settings

Ensure the following settings in your GitHub repository:

1. Go to Settings → Pages
2. Source: GitHub Actions
3. Custom domain (optional): Enter your domain

### Vite Configuration

The `vite.config.js` includes:

```javascript
{
  base: '/TanabeSugano/',  // GitHub repo name
  build: {
    outDir: '../docs',      // Output directory
  }
}
```

**Important:** If you fork this repo, update the `base` path to match your repository name.

### GitHub Actions Workflow

The workflow file `.github/workflows/deploy-pages.yml` handles:

- Node.js setup (v20)
- Dependency installation
- Site building
- Deployment to GitHub Pages

## Adding New Diagrams

To add new diagrams to the site:

1. Add HTML and CSV files to the appropriate `ts-diagrams/d*/` directory
2. Follow the naming convention:
   - `TS-diagram_d{N}_10Dq_{value}_B_{value}_C_{value}.html`
   - `DD-energies_d{N}_10Dq_{value}_B_{value}_C_{value}.html`
   - Corresponding `.csv` files

3. The build process will automatically:
   - Detect the new files
   - Add them to the index
   - Include them in the site

## Troubleshooting

### Site not updating after push

1. Check Actions tab for workflow status
2. Verify the workflow completed successfully
3. Allow 1-2 minutes for GitHub Pages to update

### Diagrams not displaying

1. Verify HTML files are in `ts-diagrams/` directory
2. Check file naming matches the expected pattern
3. Rebuild the index: `npm run generate-index`

### Build errors

1. Check Node.js version (should be 20+)
2. Delete `node_modules/` and reinstall:
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

### Base path issues

If diagrams aren't loading:
1. Verify `base` in `vite.config.js` matches your repo name
2. Ensure `.nojekyll` file exists in `docs/` directory

## Maintenance

### Updating Dependencies

```bash
cd docs-site
npm update
npm run build
```

Test locally before committing.

### Updating Diagram Index

If diagram files are reorganized:

```bash
cd docs-site
npm run generate-index
npm run build
```

## Credits

- **Diagrams:** Based on studies by Yukito Tanabe and Satoru Sugano (1954-1956)
- **Python Package:** [TanabeSugano](https://github.com/Anselmoo/TanabeSugano)
- **Author:** Anselm Hahn

## License

This project is licensed under the MIT License - see the LICENSE file for details.
