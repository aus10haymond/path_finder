# Insurance Agent Lead Finder — Full System Architecture

---

## What This System Does (Plain English)

This system is a tool built specifically for a damage restoration company owner. Instead of spending hours searching Google for insurance agents city by city, you open a simple app on your phone, type in the cities you want to target, set where you are starting and ending your trip, and hit "Generate."

The system then:

1. **Finds every insurance agent** in each of your target cities — including their name, office address, phone number, and website.
2. **Organizes the data** into a Google Sheet with a separate tab for each city, plus one master tab with everyone combined.
3. **Plans your driving route** — the most efficient path to visit every office, with a start and end point you control.
4. **Emails you a summary** with a link to your Google Sheet and your optimized route.

This replaces what would otherwise be hours of manual research and route planning with a single button press.

---

## Who Uses It and How

**User:** Restoration company owner (non-technical, mobile-first)

**Typical session:**

1. Opens the web app on his phone
2. Types in 3-10 city names (or up to 25+)
3. Types in his starting address (e.g., home or office)
4. Types in his ending address (same or different)
5. Chooses: "Route per city" or "One big route across all cities"
6. Chooses data source (if given the option) or the system picks automatically
7. Taps "Generate"
8. Gets an email within 5-15 minutes with everything ready

---

## System Components Overview

```
[Mobile Web App]
      |
      v
[Backend API Server]
      |
      |---> [Data Acquisition Layer]  --> Insurance agent data
      |---> [Google Sheets API]       --> Organizes data into spreadsheet
      |---> [Route Optimization API]  --> Plans optimal driving path
      |---> [Gmail API]               --> Sends email notification
```

---

## Detailed Component Breakdown

### 1. Frontend — Mobile Web App

**What it is:** A simple, clean website that works great on a phone. No app download required — just open a link in your browser.

**What it contains:**
- City input field (type a city, press Enter to add more, remove with X)
- Starting address field (with autocomplete)
- Ending address field (with autocomplete, or checkbox "Same as start")
- Route type toggle: "Per City" vs "All Cities Combined"
- Data source selector (optional, can be hidden for simplicity)
- "Generate" button
- Progress indicator (shows what the system is doing while it runs)
- Results summary when complete

**Technical details:**
- Built with React (or plain HTML/CSS/JS for simplicity)
- Hosted on Vercel or Railway (free tier available)
- Communicates with the backend via REST API
- Polling or WebSocket for real-time progress updates
- Fully responsive, touch-optimized

---

### 2. Backend API Server

**What it is:** The brain of the system. It receives the request from the app, coordinates all the other services, and ties everything together.

**What it does:**
- Receives the city list, start/end points, and preferences from the frontend
- Spins up a background job (so the user doesn't have to wait on a loading screen)
- Calls the data acquisition service for each city
- Deduplicates results (same agent appearing multiple times)
- Sends data to Google Sheets
- Sends the route request to the routing service
- Triggers the email notification
- Reports progress back to the frontend

**Technical details:**
- Language: Python (FastAPI) or Node.js (Express)
- Hosted on Railway, Render, or Fly.io (free tiers available)
- Uses background task queuing (Celery + Redis, or simple asyncio for lighter loads)
- Stateless API design — each request is self-contained
- Environment variables store all API keys securely

**Key API endpoints:**
```
POST /api/generate        — Starts a new generation job
GET  /api/status/{job_id} — Check job progress
GET  /api/jobs            — List past jobs
```

---

### 3. Data Acquisition Layer

**What it is:** The part of the system that goes out and finds insurance agents. This is the most technically complex piece, and the one with the most tradeoffs.

**The core challenge:** There is no single perfect, free database of every insurance agent in every city. Every option involves some tradeoff between cost, coverage, and reliability.

---

#### Option A: Google Places API (Recommended Paid Option)

**How it works:** Google's Places API lets you search for businesses by type and location. You search for "insurance agent" in a city, and Google returns a list of businesses with names, addresses, phone numbers, websites, and ratings.

**Pros:**
- Most reliable and accurate data
- Well-maintained, Google-quality results
- Easy to implement
- Returns structured data (no parsing needed)

**Cons:**
- Costs money per request (~$17 per 1,000 requests)
- Not truly exhaustive — Google indexes what it knows
- 20 results per call maximum, so large cities require multiple overlapping searches (geo-tiling)

**Estimated cost for 25 cities:** $5–25 per run depending on city size and number of agents found.

**Geo-tiling strategy for large cities:**
```
For each city:
  1. Get city bounding box (lat/lng corners)
  2. Divide into a grid of search circles
  3. Search each circle for "insurance agent"
  4. Merge and deduplicate results
```

---

#### Option B: Outscraper (Recommended One-Time / Occasional Use)

**How it works:** Outscraper is a service that does Google Maps scraping for you via a simple API. You pay per record retrieved.

**Pros:**
- Very easy to use — one API call per city
- Returns rich data including reviews, hours, photos
- Pay-per-use, no monthly subscription needed
- Good for ad-hoc runs (not daily automation)

**Cons:**
- Not free (~$0.001–0.003 per record; 500 agents = ~$0.50–1.50)
- Dependent on a third-party service
- Rate limits on free tier

**Estimated cost for 25 cities:** $2–15 total depending on agent density.

---

#### Option C: SerpApi (Free Tier Available)

**How it works:** SerpApi scrapes Google Maps search results. The free tier allows 100 searches per month.

**Pros:**
- Free tier for low-volume use
- Structured JSON output
- Reliable

**Cons:**
- 100 searches/month free (1 search = ~20 results, may need multiple per city)
- Paid tiers: $50–75/month if you exceed free limits
- Not suitable for frequent large runs

---

#### Option D: Direct Web Scraping (Free, High Effort)

**How it works:** Python + Playwright or Selenium to programmatically visit Google Maps, Yellow Pages, or Yelp and extract agent listings.

**Pros:**
- Free (no per-request cost)
- No third-party dependency

**Cons:**
- Legally gray (Google's ToS prohibits scraping)
- Fragile — breaks when the website changes its layout
- Requires significant maintenance
- Slower and less reliable
- Google actively detects and blocks scrapers

**Verdict:** Not recommended for a production tool. The dev time and maintenance cost exceeds the savings.

---

#### Option E: State Insurance Department Data (Free, Inconsistent)

**How it works:** Many state insurance departments publish online directories of licensed agents. These can sometimes be scraped or downloaded.

**Pros:**
- Official, authoritative data
- Truly comprehensive within the state
- Free

**Cons:**
- Inconsistent across states — some have good data portals, some don't
- Data formats vary widely (PDF, HTML, database search, etc.)
- Often missing physical addresses or contact info
- Would require a custom scraper per state
- Data may be stale

**Verdict:** Worth investigating as a supplementary source, but not reliable enough to be the primary source.

---

#### Recommended Strategy

| Use Case | Recommended Source |
|---|---|
| One-time setup, budget-conscious | Outscraper ($2–15 total) |
| Frequent use (weekly/monthly runs) | Google Places API (~$5–25/run) |
| Very tight budget, low volume | SerpApi free tier |
| Supplementary data | State insurance dept. databases |

The system should be built to support any of these sources via a configuration flag, so you can switch between them without rebuilding anything.

---

### 4. Google Sheets Integration

**What it is:** The system automatically creates and populates a Google Sheet with all the agent data.

**Sheet structure:**

```
Workbook: "Insurance Agents — [Date]"
  Tab: "All Cities"         ← Master list of every agent
  Tab: "Phoenix, AZ"        ← Agents in Phoenix
  Tab: "Scottsdale, AZ"     ← Agents in Scottsdale
  Tab: "Gilbert, AZ"        ← Agents in Gilbert
  ... (one tab per city)
```

**Column structure (each tab):**
```
| Agent Name | Business Name | Address | City | Phone | Website | Rating | Source |
```

**Technical details:**
- Uses Google Sheets API v4
- Requires a Google Service Account (free) with write access to a shared folder
- The system creates a new spreadsheet for each run (or overwrites a designated one)
- Tab names are auto-generated from city names
- Data is sorted by agent name within each tab
- Conditional formatting applied automatically (alternating row colors for readability)

**Setup requirement:** One-time Google Cloud project setup + service account creation. Takes ~30 minutes. After that, fully automatic.

---

### 5. Route Optimization

**What it is:** Given a list of addresses, the system figures out the most efficient order to visit them all, minimizing total drive time.

**This is the "Traveling Salesman Problem"** — mathematically complex, but well-solved by modern APIs.

**Route options:**

#### Per-City Route
- Optimizes visits within one city at a time
- Start point → visit all agents in City A in optimal order → End point
- Generates one route per city
- More practical for a day's work

#### All-Cities Route
- One mega-route across all cities
- Optimal for a multi-day road trip
- Start point → all agents across all cities in optimal order → End point
- For very large lists (150+ stops), the system automatically batches and chains route segments

**API options:**

| Option | Cost | Max Stops | Notes |
|---|---|---|---|
| OpenRouteService | Free (2,000 req/day) | 50 per request | Best free option |
| RouteXL | Free up to 20 stops; $10/mo beyond | Unlimited (paid) | Simple, reliable |
| Google Maps Routes API | ~$10 per 1,000 requests | 25 per request (chains) | Most accurate |
| OSRM (self-hosted) | Free | Unlimited | Requires server setup |

**Recommended:** OpenRouteService for free, Google Maps Routes API if accuracy matters.

**Output format:**
```
Optimized Route — Phoenix, AZ
Total stops: 34
Estimated drive time: 4h 20min
Estimated distance: 87 miles

Stop 1: State Farm — Jane Smith
         4521 E Thomas Rd, Phoenix, AZ 85018
         (602) 555-0123

Stop 2: Allstate — Robert Garcia
         1892 W Camelback Rd, Phoenix, AZ 85015
         (602) 555-0456
...
```

**Large list handling (150+ stops):**
```
1. Cluster stops geographically (k-means clustering)
2. Optimize route within each cluster
3. Chain clusters in logical geographic order
4. Merge into a single continuous route
```

---

### 6. Email Notification

**What it is:** When the job is complete, the system sends an email to the user with everything they need.

**Email contents:**
- Subject: "Your Insurance Agent List is Ready — [City Count] Cities, [Agent Count] Agents"
- Summary: how many agents were found per city
- Link to the Google Sheet (clickable)
- Route summary for each city (or the combined route)
- Link to open the route in Google Maps
- Date/time generated

**Technical details:**
- Uses Gmail API via a service account, or SendGrid free tier (100 emails/day free)
- HTML-formatted email for clean presentation
- Google Maps deep link: `https://www.google.com/maps/dir/?api=1&waypoints=...`
- Email delivered within seconds of job completion

---

## Data Flow — Step by Step

```
User taps "Generate" on phone
        |
        v
Frontend sends POST request to backend API
  { cities: ["Phoenix", "Scottsdale"], start: "123 Main St", end: "123 Main St", mode: "per_city" }
        |
        v
Backend creates a job ID, returns it immediately
Frontend begins polling for status updates
        |
        v
Background worker starts:
  For each city:
    [1] Call data acquisition API (Google Places / Outscraper / SerpApi)
    [2] Parse and clean results
    [3] Deduplicate (remove duplicates across search tiles)
    [4] Add to master agent list
        |
        v
  [5] Write all data to Google Sheets
      - Create new spreadsheet
      - Create "All Cities" tab with full list
      - Create one tab per city
      - Apply formatting
        |
        v
  [6] For each city (or all combined):
      - Send addresses to route optimizer
      - Receive ordered stop list + drive time
        |
        v
  [7] Compose and send email
      - Link to Google Sheet
      - Route details per city
      - Google Maps links
        |
        v
  [8] Mark job as complete
        |
        v
Frontend shows "Done!" with link to sheet and route summary
```

---

## Infrastructure — Where Everything Lives

| Component | Service | Cost |
|---|---|---|
| Frontend (web app) | Vercel | Free |
| Backend API | Railway or Render | Free tier (500 hrs/mo) |
| Database (job tracking) | SQLite (file) or Supabase | Free |
| Background jobs | asyncio (built into Python) | Free |
| Google Sheets | Google Cloud (Service Account) | Free |
| Gmail | Gmail API | Free |
| Route optimization | OpenRouteService | Free |
| Data acquisition | Outscraper / Places API | $2–25/run |

**Total ongoing infrastructure cost: $0/month** (excluding per-run data acquisition cost)

---

## Security Considerations

- All API keys stored as environment variables (never in code)
- Google Service Account has minimal permissions (only Sheets + Gmail)
- The web app has no login — a secret URL acts as basic access control (simple, appropriate for personal use)
- No user data stored beyond job logs (city names, timestamps, agent counts)
- Agent data written directly to Google Sheets — not stored on the server

---

## Scalability

The system is designed for personal/small business use. Current design handles:
- Up to 25+ cities per run
- Up to ~500 agents per run comfortably
- 1-2 concurrent users
- Multiple runs per day

If the business grows and this needs to scale to a multi-user product, the architecture supports:
- Adding authentication (Auth0 or Supabase Auth)
- Moving to a proper task queue (Celery + Redis)
- Adding a database for storing historical results
- Upgrading to paid API tiers for higher volume

---

## Development Phases

### Phase 1 — Core MVP (2-4 weeks)
- [ ] Backend API with job tracking
- [ ] One data source (Outscraper recommended)
- [ ] Google Sheets integration
- [ ] Basic email notification
- [ ] Simple frontend (city list + generate button)

### Phase 2 — Route Optimization (1-2 weeks)
- [ ] OpenRouteService integration
- [ ] Per-city and all-cities route modes
- [ ] Start/end point configuration
- [ ] Route included in email

### Phase 3 — Polish (1-2 weeks)
- [ ] Real-time progress updates in the frontend
- [ ] Multiple data source support with fallback
- [ ] Mobile UI refinement
- [ ] Error handling and retry logic

### Phase 4 — Optional Enhancements
- [ ] Save and reload past runs
- [ ] Filter agents by agency type (State Farm, Allstate, independent, etc.)
- [ ] Export route to Google Maps or Waze directly
- [ ] Scheduling (run automatically on a schedule)

---

## Open Questions / Decisions to Make

1. **Data source:** Outscraper (easiest, small cost) vs Google Places API (more control, similar cost) vs SerpApi free tier (free but limited)?
2. **Route optimizer:** OpenRouteService (free, easy) vs Google Maps Routes API (more accurate, small cost)?
3. **Email delivery:** Gmail API (uses existing Gmail account) vs SendGrid (dedicated sending service)?
4. **Frontend complexity:** Ultra-simple (one page, no auth) vs slightly richer (history of past runs, saved cities)?
5. **Starting point for dev:** Build backend first and test via Postman, or build a working frontend prototype first?

---

*Document version 1.0 — Architecture subject to change based on decisions above.*
