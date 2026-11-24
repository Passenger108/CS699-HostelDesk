# HostelDesk

HostelDesk is an application for Hostel 4, IIT Bombay. It targets to replace the old-fashioned paper register entry including WhatsApp messages being used to broadcast requests to a worker group, where works collaboratively or per say mutually decides among themselves, like who shall go for that raised request. Yeah, I know it sounds a bit 90s, but don't worry, here we are......

... PROPOSING A SOLUTION for it, a 21st century standard solution.


Basically, it is simple to explain. You will relate it with modern advancements and digitalizations.

 Our app digitalize the overall workflows and makes everything transparent to students so accountibility remains the first citizen.
 Hurray! its time to suppress the workers and bring a solution to suppress the already suppressed ones and call it a digital product.


Four kinds of users:

- **Students** ask for a cleaning, choose when they are free, follow the job live, confirm or dispute the result, and leave a rating.
- **Workers** receive job offers, accept them with an arrival time, report delays or problems, upload a photo as proof, and see their queue and ratings.
- **Supervisors** approve requests, pick a worker (with suggestions based on where workers are), handle delays and disputes, and see monthly reports.
- **The Super Admin** manages accounts and the hostel layout, and can search the full audit record.

Release 1 covers: sign in, weekly cleaning credits, requests with preferred time windows, supervisor approval and worker offers, arrival time (ETA) and delay tracking, a chat for each job, photo proof with a server time stamp, student confirm or dispute, star ratings, notifications, an audit log, and an anonymised monthly report with CSV download.

## Tech stack

| Part | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, TanStack React Query |
| Backend | Python, Flask 3, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-JWT-Extended |
| Security | Argon2 password hashing, JWT access and refresh tokens, login rate limiting (Flask-Limiter), CORS |
| Images | Pillow (resizes proof photos and stamps them with the server time) |
| Database | SQLite for local development (PostgreSQL supported through `DATABASE_URL`) |

The frontend runs at http://localhost:5173 and the backend at http://localhost:5001. During development Vite forwards every `/api/...` call to the backend, so the browser sees a single site.

## How the code is organised

The backend is split into **modules**, one per area of the system (auth, cleaning, credits, and so on). Inside a module, files follow the same pattern:

- `models.py` defines the database tables.
- `service.py` (and other named files such as `arrival.py`) holds the business rules.
- `schemas.py` turns database rows into the JSON the frontend receives.
- `routes.py` defines the web addresses (API endpoints), checks who is allowed to call them, and calls the service.

The frontend mirrors this: `src/api/` has one file of API calls per backend module, `src/types/` has the matching data shapes, and `src/features/` has the screens, grouped by area.

## Folder structure

```
HostelDesk/
├── README.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── .gitignore
│   ├── requirements.txt
│   ├── wsgi.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── extensions.py
│   │   ├── cli.py
│   │   ├── auth/              guards.py, passwords.py, routes.py, service.py
│   │   ├── cleaning/          models.py, workflow.py, service.py, arrival.py, delays.py,
│   │   │                      completion.py, messages.py, feedback.py, recommendations.py,
│   │   │                      timers.py, schemas.py, routes.py
│   │   ├── common/            audit.py, errors.py, models.py, settings.py, storage.py, time.py
│   │   ├── credits/           models.py, service.py, schemas.py, routes.py
│   │   ├── hostel_structure/  models.py, service.py, schemas.py, routes.py
│   │   ├── notifications/     models.py, service.py, schemas.py, routes.py
│   │   ├── reports/           audit.py, service.py, routes.py
│   │   ├── users/             models.py, service.py, schemas.py, routes.py, admin_routes.py
│   │   └── workers/           service.py, schemas.py, routes.py
│   └── migrations/
│       ├── alembic.ini
│       ├── env.py
│       ├── script.py.mako
│       └── versions/          12 numbered database changes
└── frontend/
    ├── .gitignore
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── eslint.config.js
    └── src/
        ├── main.tsx
        ├── api/               one file of API calls per backend area
        ├── app/               app root, router, layout, access guards
        ├── components/        shared pieces
        ├── features/          screens, grouped by area
        ├── pages/             fallback pages
        ├── theme/             global.css
        ├── types/             data shapes returned by the API
        └── utils/             format.ts
```

Every Python package folder also has an empty `__init__.py`, which marks the folder as a Python package.

## Role of each file

### Root

| File | Role |
|---|---|
| `README.md` | This guide. |
| `.gitignore` | Tells Git to ignore operating system and editor files. |

### backend/

| File | Role |
|---|---|
| `.env.example` | Sample settings file. Copy it to `.env` and fill in secret keys before running. |
| `.gitignore` | Keeps the virtual environment, `.env`, the local database, uploaded photos and Python caches out of Git. |
| `requirements.txt` | The Python libraries the backend needs, with exact versions. |
| `wsgi.py` | Entry point. Builds the Flask app so `flask run` (or a production server) can start it. |

### backend/app/

| File | Role |
|---|---|
| `__init__.py` | The app factory: loads settings, connects the extensions, registers every module's routes under `/api/v1`, adds the `/api/v1/health` check, and starts the background timers. |
| `config.py` | Settings for development and production (secret keys, database address, token lifetimes, upload limits, login lock rules). |
| `extensions.py` | Creates the shared Flask extensions: database, migrations, JWT, rate limiter and CORS. |
| `cli.py` | Extra `flask` commands: `seed-demo` (hostel layout and demo accounts), `seed-demo-requests` (sample jobs in every stage), `grant-weekly-credits` and `run-timers`. |

### backend/app/auth/ (signing in and access control)

| File | Role |
|---|---|
| `guards.py` | `@login_required` and `@roles_required(...)` decorators used by every route, plus `current_user()`. |
| `passwords.py` | Hashes and checks passwords with Argon2. |
| `service.py` | Login logic: checks the password, counts failed attempts, locks the account after too many failures, and issues tokens. |
| `routes.py` | Endpoints for login and token refresh. |

### backend/app/cleaning/ (the main cleaning workflow)

| File | Role |
|---|---|
| `models.py` | Tables for cleaning requests, the request timeline (events), worker offers, proof photos, chat messages and feedback, plus the list of request statuses. |
| `workflow.py` | The rulebook of the request's life: which status can move to which, who may make each move, and recording each step on the timeline. |
| `service.py` | Core request actions: submit, cancel, approve, edit, offer to a worker, accept or decline an offer, take back, and the supervisor's operations board. |
| `arrival.py` | The worker's trip: setting off, arriving, the door response (student home or not), and starting the cleaning. |
| `delays.py` | Late workers, missed time windows, rescheduling and the supervisor's decisions on reported problems. |
| `completion.py` | Proof photo upload, the completion checklist, student confirm or dispute, automatic close, and dispute decisions. |
| `messages.py` | The text chat attached to each job. |
| `feedback.py` | Star ratings and comments that students leave after a job, and a worker's rating summary. |
| `recommendations.py` | Ranks workers for a request by availability, distance from the room and current workload, with a short reason for each. |
| `timers.py` | Background loop that runs every 15 seconds to expire offers, close waits, escalate delays and grant weekly credits. |
| `schemas.py` | Turns requests, events, offers and related records into JSON for the frontend. |
| `routes.py` | All `/api/v1/cleaning/...` endpoints for students, workers and supervisors. |

### backend/app/common/ (shared helpers)

| File | Role |
|---|---|
| `audit.py` | The audit log table and the helper that records who did what and when. |
| `errors.py` | The list of error codes and messages, and the handler that returns them as JSON. |
| `models.py` | Shared table pieces (id, created and updated times) and UTC time helpers. |
| `settings.py` | Versioned system settings, such as the credit limit, with default values. |
| `storage.py` | Saves proof photos to disk, shrinks them and stamps the server time on them. |
| `time.py` | Hostel local time (India) and date helpers used by timers and credits. |

### backend/app/credits/ (weekly cleaning credits)

| File | Role |
|---|---|
| `models.py` | The credit ledger table (every credit added or spent). |
| `service.py` | Balance, weekly grants up to a limit, goodwill credits, and reserving, using or returning a credit for a request. |
| `schemas.py` | Turns ledger entries into JSON for the credits history. |
| `routes.py` | Endpoint for a student's balance and history. |

### backend/app/hostel_structure/ (the building)

| File | Role |
|---|---|
| `models.py` | Tables for the hostel, floors, wings, rooms and worker locations. |
| `service.py` | Creates the Hostel 4 layout and looks up rooms and locations. |
| `schemas.py` | Turns the building layout into JSON. |
| `routes.py` | Endpoints for the hostel layout and list of locations. |

### backend/app/notifications/

| File | Role |
|---|---|
| `models.py` | The notifications table. |
| `service.py` | Creates the right notification for each person when a request changes. |
| `schemas.py` | Turns notifications into JSON. |
| `routes.py` | Endpoints to list notifications, count unread ones and mark them read or unread. |

### backend/app/reports/

| File | Role |
|---|---|
| `audit.py` | Search and filtering of the audit log for the Super Admin. |
| `service.py` | Builds the anonymised monthly report (requests, times, disputes, ratings) and its CSV version. |
| `routes.py` | Endpoints for the monthly report and CSV download. |

### backend/app/users/ (accounts and profiles)

| File | Role |
|---|---|
| `models.py` | Tables for users, student profiles and worker profiles, and the list of roles. |
| `service.py` | Super Admin account management: list accounts, create new ones with checks (unique IDs, room space), and activate or deactivate them. |
| `schemas.py` | Turns a user's profile into JSON. |
| `routes.py` | Endpoint for the signed-in user's own profile (`/me`). |
| `admin_routes.py` | Super Admin endpoints for managing people and reading the audit log. |

### backend/app/workers/

| File | Role |
|---|---|
| `service.py` | Worker locations, on-duty and off-duty status, stale-location reminders and the worker's task list. |
| `schemas.py` | Turns workers, their queue and their offers into JSON. |
| `routes.py` | Endpoints for the worker list, locations, queue order, off-duty requests, a worker's ratings, and accepting or declining offers. |

### backend/migrations/ (database history)

| File | Role |
|---|---|
| `alembic.ini` | Settings for Alembic, the migration tool. |
| `env.py` | Connects Alembic to the Flask app and its tables. |
| `script.py.mako` | Template used when a new migration file is generated. |
| `versions/*.py` | Twelve migration files that build the database step by step: users and login, hostel structure and profiles, credits and audit log, cleaning requests and events, offers, notifications, worker queue position, arrival response, delay state, proof photos and checklist, chat and feedback, and removal of an unused contact field. `flask db upgrade` applies them in order. |

### frontend/

| File | Role |
|---|---|
| `.gitignore` | Keeps `node_modules`, the build output and local env files out of Git. |
| `index.html` | The single HTML page the app is loaded into. |
| `package.json` | Frontend libraries and the `dev`, `build`, `preview` and `lint` commands. |
| `package-lock.json` | Exact versions of every installed library, so installs are repeatable. |
| `tsconfig.json` | TypeScript compiler settings (strict type checking). |
| `vite.config.ts` | Vite settings: dev server on port 5173 and forwarding of `/api` calls to the backend on port 5001. |
| `eslint.config.js` | Code style checks run by `npm run lint`. |

### frontend/src/

| File | Role |
|---|---|
| `main.tsx` | Starts React and loads the global styles. |

### frontend/src/app/ (app frame and navigation)

| File | Role |
|---|---|
| `App.tsx` | Root component: wraps the router in the app's providers. |
| `providers.tsx` | Sets up React Query and the sign-in context for every screen. |
| `router.tsx` | Maps every web address to its screen and applies the access guards. |
| `AppShell.tsx` | The page frame: top bar, side menu, notification bell and sign out. |
| `navigation.ts` | The menu items shown to each role. |
| `RequireAuth.tsx` | Sends users who are not signed in to the login page. |
| `RequireRole.tsx` | Blocks screens that the user's role may not open. |

### frontend/src/api/ (calls to the backend)

| File | Role |
|---|---|
| `client.ts` | The shared `apiFetch` helper: adds the sign-in token, refreshes it when it expires and turns errors into messages. |
| `auth.ts` | Login and token refresh calls. |
| `cleaning.ts` | Calls for requests, workflow steps, proof, chat and feedback. |
| `credits.ts` | Call for the credit balance and history. |
| `hostel.ts` | Calls for the hostel layout and locations. |
| `notifications.ts` | Calls to list, count and mark notifications. |
| `profile.ts` | Call for the signed-in user's profile. |
| `workers.ts` | Calls for workers, locations, queues and offers. |
| `admin.ts` | Super Admin calls for people management and the audit log. |
| `reports.ts` | Calls for the monthly report and CSV download. |

### frontend/src/types/ (data shapes)

| File | Role |
|---|---|
| `user.ts` | Signed-in user and roles. |
| `profile.ts` | Student and worker profile details. |
| `hostel.ts` | Rooms, locations and the building layout. |
| `credits.ts` | Credit balance and ledger entries. |
| `cleaning.ts` | Requests, timeline events, offers, delays, proof and the operations board. |
| `notification.ts` | A notification. |
| `worker.ts` | Workers, queue rows, recommendations and offers. |
| `audit.ts` | Audit log entries and filters. |
| `report.ts` | The monthly report. |

### frontend/src/features/ (screens)

| File | Role |
|---|---|
| `auth/AuthContext.tsx` | Keeps the signed-in user and tokens, and provides login and logout to every screen. |
| `auth/LoginPage.tsx` | The sign-in screen. |
| `home/HomePage.tsx` | Chooses the right home screen for the user's role. |
| `cleaning/RequestCleaningPage.tsx` | Student form to ask for a cleaning (normal or urgent) with preferred times. |
| `cleaning/AvailabilityFields.tsx` | The time-window inputs shared by the request and reschedule forms. |
| `cleaning/ActiveRequestCard.tsx` | Card showing a request's status, details and the actions available to the viewer. |
| `cleaning/RequestDetailPage.tsx` | Full page for one request. |
| `cleaning/RequestTimeline.tsx` | The list of every step a request went through. |
| `cleaning/TaskSteps.tsx` | Buttons for the worker's steps (set off, arrived, start, report a problem). |
| `cleaning/RescheduleForm.tsx` | Form to pick a new time after a missed window. |
| `cleaning/CompletionPanel.tsx` | Proof upload and checklist for the worker; confirm or dispute for the student; decision for the supervisor. |
| `cleaning/ProofImage.tsx` | Loads and shows a proof photo securely. |
| `cleaning/TaskChat.tsx` | The chat box for a job. |
| `cleaning/FeedbackPanel.tsx` | Star rating form shown to the student after a job. |
| `cleaning/HistoryPage.tsx` | A student's past requests. |
| `cleaning/StatusChip.tsx` | Coloured label for a request's status. |
| `cleaning/labels.ts` | Readable names for statuses and event types. |
| `credits/CreditsCard.tsx` | Small balance card on the student's home screen. |
| `credits/CreditsPage.tsx` | Full credits balance and history. |
| `credits/labels.ts` | Readable names for credit entry types. |
| `operations/OperationsPage.tsx` | The supervisor's board of all open requests, grouped by stage. |
| `operations/SupervisorActions.tsx` | The supervisor's buttons on a request (approve, assign, cancel, decide). |
| `operations/AssignPanel.tsx` | Picks a worker for a request, showing recommended workers first. |
| `operations/TakeBackForm.tsx` | Takes a job back from a worker and reassigns it. |
| `workers/WorkerHome.tsx` | The worker's home screen: offers, queue, location and ratings. |
| `workers/OfferCard.tsx` | One job offer with accept (with ETA) and decline. |
| `workers/TaskQueue.tsx` | A worker's list of accepted jobs. |
| `workers/LocationForm.tsx` | Sets a worker's current floor and wing. |
| `workers/MyRatings.tsx` | A worker's average rating and recent comments. |
| `workers/WorkersPage.tsx` | Supervisor view of all workers, their place, queue and rating. |
| `notifications/NotificationBell.tsx` | Bell icon with the unread count in the top bar. |
| `notifications/NotificationsPage.tsx` | The full list of notifications. |
| `profile/ProfilePage.tsx` | The user's own profile and settings. |
| `hostel/HostelStructurePage.tsx` | Super Admin view of floors, wings and rooms. |
| `admin/PeoplePage.tsx` | Super Admin screen to create and manage accounts. |
| `admin/AuditPage.tsx` | Super Admin search of the audit log. |
| `reports/ReportsPage.tsx` | Monthly report table with CSV download. |

### frontend/src/ (other folders)

| File | Role |
|---|---|
| `components/ErrorMessage.tsx` | Shows an error message in a consistent style. |
| `pages/NotFoundPage.tsx` | Page shown for an unknown address. |
| `pages/SectionPage.tsx` | Simple placeholder page for sections a role does not use. |
| `theme/global.css` | All app styles: colours, layout, cards, forms and mobile layout. |
| `utils/format.ts` | Date and time formatting in hostel local time. |

## Running it locally

You need **Python 3.10 to 3.13** (3.12 recommended; the PostgreSQL driver has no Python 3.14 build yet) and **Node.js 20 or newer**. Use two terminal windows.

### 1. Backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Open `.env` and replace the two secret values with any long random text (at least 32 characters each). Then:

```bash
flask db upgrade                   # creates the database tables
flask seed-demo                    # adds the Hostel 4 layout and demo accounts
flask seed-demo-requests           # optional: sample requests in different stages
flask run                          # starts the backend on http://localhost:5001
```

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                        # starts the app on http://localhost:5173
```

Open http://localhost:5173 in a browser. `flask seed-demo` prints the demo password. Sign in as `demo.student`, `demo.worker`, `demo.supervisor` or `demo.admin` to see each role.

To make a production build of the frontend, run `npm run build`. The output goes to `frontend/dist/`.

