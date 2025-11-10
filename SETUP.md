# Setting Up GitHub Pages for Tanabe-Sugano Diagrams

This guide walks you through enabling GitHub Pages for this repository.

## Prerequisites

- Repository must be public or you must have GitHub Pro/Team/Enterprise
- You must have admin access to the repository

## Step-by-Step Setup

### 1. Enable GitHub Pages

1. Go to your repository on GitHub: https://github.com/Anselmoo/TanabeSugano
2. Click on **Settings** (top navigation)
3. In the left sidebar, click **Pages**
4. Under **Build and deployment**:
   - **Source**: Select **GitHub Actions**
   - This allows the workflow in `.github/workflows/deploy-pages.yml` to deploy the site

### 2. Verify Workflow Permissions

1. Still in **Settings**, go to **Actions** → **General** (in left sidebar)
2. Scroll to **Workflow permissions**
3. Ensure **Read and write permissions** is selected
4. Check **Allow GitHub Actions to create and approve pull requests**
5. Click **Save**

### 3. Trigger Initial Deployment

Option A: Push to master branch
```bash
git push origin master
```

Option B: Manual workflow trigger
1. Go to **Actions** tab
2. Click **Deploy GitHub Pages** workflow
3. Click **Run workflow**
4. Select `master` branch
5. Click **Run workflow**

### 4. Wait for Deployment

1. Go to **Actions** tab
2. You should see a workflow run in progress
3. Wait for both **build** and **deploy** jobs to complete (usually 1-2 minutes)
4. Look for a green checkmark ✓

### 5. Access Your Site

Once deployed, your site will be available at:
- **URL**: https://anselmoo.github.io/TanabeSugano/

You can find the exact URL in:
- **Settings** → **Pages** → **Your site is live at...**
- Or in the workflow run details under the deploy job

## Troubleshooting

### "Deploy to GitHub Pages" step fails

**Error**: `Error: No deployment token found`

**Solution**: 
1. Go to **Settings** → **Pages**
2. Ensure **Source** is set to **GitHub Actions** (not "Deploy from a branch")

### Workflow doesn't run automatically

**Possible causes**:
1. Workflow file is not in `master` branch
2. File path is incorrect (must be `.github/workflows/deploy-pages.yml`)
3. Permissions are not set correctly

**Solution**:
1. Verify the workflow file exists:
   ```bash
   git ls-tree -r master --name-only | grep deploy-pages.yml
   ```
2. Check workflow permissions (see Step 2 above)

### Site shows 404 error

**Possible causes**:
1. Deployment hasn't completed yet
2. Base URL in `vite.config.js` doesn't match repository name
3. `.nojekyll` file is missing

**Solution**:
1. Wait a few minutes after deployment completes
2. Verify `base: '/TanabeSugano/'` in `docs-site/vite.config.js` matches your repo name
3. Ensure `docs/.nojekyll` exists (created during build)

### Diagrams don't load

**Possible causes**:
1. `ts-diagrams` folder wasn't copied during build
2. Paths in React app are incorrect

**Solution**:
1. Check the workflow includes the "Copy diagram files" step
2. Verify `docs/ts-diagrams/` directory exists and contains files
3. Rebuild: `cd docs-site && npm run build`

### Changes don't appear on the site

**Possible causes**:
1. Browser cache
2. GitHub Pages cache (can take 1-2 minutes)
3. Changes weren't pushed to master

**Solution**:
1. Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)
2. Wait 2-3 minutes after workflow completes
3. Verify changes are in master branch:
   ```bash
   git log --oneline -1 origin/master
   ```

## Custom Domain (Optional)

To use a custom domain:

1. **Settings** → **Pages**
2. Under **Custom domain**, enter your domain (e.g., `diagrams.example.com`)
3. Click **Save**
4. Update your DNS provider:
   - Add a CNAME record pointing to `anselmoo.github.io`
5. Wait for DNS propagation (can take up to 24 hours)
6. Once verified, check **Enforce HTTPS**

Then update `vite.config.js`:
```javascript
export default defineConfig({
  plugins: [react()],
  base: '/',  // Change from '/TanabeSugano/' to '/'
  build: {
    outDir: '../docs',
  },
})
```

Rebuild and redeploy:
```bash
cd docs-site
npm run build
git add ../docs
git commit -m "Update for custom domain"
git push
```

## Monitoring

### Check Deployment Status

1. **Actions** tab shows all workflow runs
2. Each run shows:
   - Build logs
   - Deployment URL
   - Success/failure status

### Analytics (Optional)

To add Google Analytics or other analytics:

1. Edit `docs-site/index.html`
2. Add your analytics script before `</head>`
3. Rebuild and commit:
   ```bash
   cd docs-site
   npm run build
   git add .
   git commit -m "Add analytics"
   git push
   ```

## Maintenance

### Updating Dependencies

Periodically update Node.js dependencies:

```bash
cd docs-site
npm update
npm audit fix
npm run build
git add .
git commit -m "Update dependencies"
git push
```

### Adding New Diagrams

1. Add diagram files to appropriate `ts-diagrams/d*/` directory
2. Follow naming convention: `TS-diagram_d{N}_10Dq_{value}_B_{value}_C_{value}.html`
3. The build process automatically indexes new diagrams
4. Push changes to master:
   ```bash
   git add ts-diagrams/
   git commit -m "Add new diagrams"
   git push
   ```

## Support

For issues or questions:
- Create an issue: https://github.com/Anselmoo/TanabeSugano/issues
- Check Actions logs for deployment errors
- Review GITHUB_PAGES.md for detailed documentation

## Summary

Once set up:
1. ✅ Every push to `master` automatically rebuilds and deploys the site
2. ✅ Site is accessible at https://anselmoo.github.io/TanabeSugano/
3. ✅ New diagrams are automatically indexed and displayed
4. ✅ No manual intervention needed for updates

The site will be live within 2-3 minutes of pushing to master!
