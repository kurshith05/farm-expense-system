# Deploy: Supabase (database) + GitHub (code) + Vercel (website)

## Part 1 - Supabase database
1. Go to https://supabase.com, sign in, click **New project**.
2. Choose a name, a region close to you (e.g. Singapore) and a **database password**.
   Use only letters and numbers (no @ : / # symbols) and save it somewhere.
3. Wait until the project is ready. Click **Connect** at the top and copy the
   **Transaction pooler** connection string. Replace `[YOUR-PASSWORD]` with your password.
   (The pooler string is the one to use for Vercel. Supabase's Connect panel explains the options.)
4. On your computer, put it in your `.env` file as `DATABASE_URL=...` (see `.env.example`).
5. Create the tables (once): `python app.py initdb`  - you should see "Database tables are ready."
6. Run `python app.py` and test the site locally. It now saves to Supabase.
   (Check in Supabase: Table Editor shows users, expenses, settings.)

## Part 2 - GitHub
1. Create a free account at https://github.com and a **New repository** (Private is fine). Do not add a README.
2. In the project folder terminal (install Git for Windows first if `git` is not found):
       git init
       git add .
       git commit -m "Farm Expense System"
       git branch -M main
       git remote add origin https://github.com/YOURNAME/YOURREPO.git
       git push -u origin main
3. On GitHub, check that `.env` and `venv` are NOT in the repository. (`.gitignore` should prevent it.)
   If your secrets ever got uploaded, change your Supabase password and SECRET_KEY.

## Part 3 - Vercel
1. Go to https://vercel.com and sign up with your GitHub account.
2. **Add New > Project**, import your repository. Vercel should detect Flask automatically.
3. Open **Environment Variables** and add:
       SECRET_KEY    = a long random text (a different one from local is fine)
       DATABASE_URL  = the same Supabase Transaction pooler string
4. Click **Deploy**. When it finishes, open the link Vercel gives you.
5. Register an account on the live site and run the test checklist in `README.md`.

## Updating later
Change code, then `git add .`, `git commit -m "message"`, `git push`. Vercel redeploys automatically.

## Before your presentation
Supabase free projects pause after about a week of no activity. Open your live site a day before.
If it shows errors, open the Supabase dashboard and click **Restore** on the paused project.

## Troubleshooting
- "DATABASE_URL is not set": add it under Vercel > Project > Settings > Environment Variables, then redeploy.
- "password authentication failed": the password in the connection string is wrong or has special characters.
- "relation users does not exist": run `python app.py initdb` with your Supabase DATABASE_URL.
- Page has no styling: make sure the `public/` folder (with `css/` and `js/`) is in your GitHub repo.
- See what went wrong: Vercel > your project > Logs.
