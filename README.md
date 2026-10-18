# KaziKE deployment (JSON route)

Files: index.html (site), jobs.json (data), job_aggregator.py (fetch + Claude cleanup), .github/workflows/update-jobs.yml (daily schedule)

1. Create a GitHub repo and upload everything in this folder (keep the .github folder).
2. Repo > Settings > Secrets and variables > Actions: add ANTHROPIC_API_KEY (and JOOBLE_KEY if you have one).
3. Actions tab > "Update jobs" > Run workflow once to test.
4. Host the repo for free on Cloudflare Pages, Netlify or GitHub Pages (publish the repo root). Each daily commit redeploys the site.
5. Buy a .co.ke domain and point it at the host.
6. jobs.json starts with fictional sample jobs. Delete them (replace the file with []) before launch.
7. To feature a job for a paying employer, set "f": 1 on its entry in jobs.json.
