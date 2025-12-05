# MySplit Backend & Mobile App

This project bundles both the Azure Functions backend and the Expo/React Native mobile client for the SplitPal expense-sharing experience:
- Python Azure Functions (HTTP triggers) with JWT auth
- SQLite for local development storage
- Groups, transactions, splits, balances, admin tooling
- React Native (Expo) mobile/front-end UI targeting Android, iOS, and web
- Shared LAN testing workflow for real devices

## Run backend locally

1. Install Azure Functions Core Tools (v4) and Python 3.10/3.11.
2. Create a virtualenv and install requirements:
   ```
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Initialize DB:
   ```
   python init_db.py
   ```
4. Start functions:
   ```
   func start
   ```
5. API endpoints are available at `http://localhost:7071/api/...` by default. When testing from other devices on your network, update your clients to point to `http://<your-lan-ip>:7071/api/...`.

## Run the mobile client

1. Install dependencies (one time per machine):
   ```
   cd mobile
   npm install
   ```
2. Start Expo in development mode:
   ```
   npm run start
   ```
3. Scan the QR code with Expo Go or press the platform shortcuts (press `a` for Android, `w` for web, etc.).
4. Ensure `EXPO_PUBLIC_API_BASE_URL` in `mobile/app.json` points to the running backend (localhost for emulators, LAN IP for physical devices).

The Postman collection (`MySplit - Full Backend Operations.postman_collection.json`) expects a `base_url` collection variable. Set it to the host/port you are targeting (e.g. `http://localhost:7071/api` or your LAN IP).

## Mobile client configuration

- Update `EXPO_PUBLIC_API_BASE_URL` in `mobile/app.json` (and `eas.json` if building with EAS) so it matches the backend base URL.
- After changing the URL, restart the Expo dev server and reload the app to flush cached endpoints.

The uploaded sample image (from your conversation) is included at: `data/1000112620.jpg`
