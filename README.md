# DentBid

Upload photos of car damage. DentBid's computer-vision engine finds every dent, scratch and crack, measures it and grades how severe it is. Nearby workshops get a precise damage report, send quotes, and the customer picks the best offer. Customers can also name their own price or counter a quote, and workshops can accept it.

One codebase runs on **Android, iOS and the web**.

## How it works

1. **Customer** takes 1-8 photos. The app checks them for blur, darkness and glare.
2. **CV engine** segments the damage (dent, scratch, crack, shattered glass, broken lamp, flat tire), finds which panel it is on, and estimates:
   - size in cm (scaled from the known size of the detected panel)
   - scratch length and paint depth (clear coat, colour coat, or primer/bare metal)
   - dent depth, from reflection distortion
   - a severity score from 0 to 100 (minor, moderate or severe), a suggested repair method and a labour estimate
3. **Workshops** inside the service radius get a notification. They see the annotated photos and the report, then quote a price, a turnaround time and a warranty.
4. **Customer** compares quotes by price, rating and distance, then accepts one or sends a counter offer. The workshop's phone number and location are only revealed after booking.
5. The workshop marks the job in progress and then completed, and the customer leaves a review.

**Locale is detected automatically:** GPS reverse-geocoding gives the country, which sets the currency and language (English, Urdu, Arabic, Hindi or Spanish, with right-to-left layout for Urdu and Arabic). Without GPS, DentBid falls back to the IP country and then the device settings. Users can change the language in their profile.

## Repository

| Folder | What |
|---|---|
| [`ml/`](ml) | `dentbid_cv` package: YOLO11 segmentation, measurement, severity grading, training pipeline and Colab notebook |
| [`backend/`](backend) | FastAPI + PostgreSQL API: auth, requests, background AI analysis, bidding, chat, WebSocket and push notifications |
| [`mobile/`](mobile) | Expo (React Native) app for Android, iOS and web |

## Quick start

### 1. Train the models (once, on a free GPU)

Open [`ml/notebooks/train_colab.ipynb`](ml/notebooks/train_colab.ipynb) in Google Colab, then put the resulting `damage.pt` and `parts.pt` in `ml/weights/`. See [ml/README.md](ml/README.md) for details.

The app also runs without weights. In that case workshops quote from the photos alone, without the AI report.

### 2. Backend

With Docker:

```bash
docker compose up --build
```

Or locally with SQLite:

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt -e "../ml[yolo]"
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0
```

The API docs are at http://localhost:8000/docs.

### 3. App

```bash
cd mobile
npm install
npx expo start
```

- Press `w` for the web app, or scan the QR code with Expo Go.
- In development the app reaches the API on your computer's LAN IP, port 8000.
- For a deployed API, set `EXPO_PUBLIC_API_URL`.
- Push notifications need a development build: `npx eas-cli build --profile development`.

## Tests

```bash
cd ml && pytest -q
cd backend && pytest -q
cd mobile && npx tsc --noEmit
```

## Author

**MIsmail2524**. Licensed under the MIT License.
