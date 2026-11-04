# DentBid

Upload photos of car damage. DentBid's computer-vision engine finds every dent, scratch and crack, measures it and grades how severe it is. Nearby workshops get a precise damage report, send quotes, and the customer picks the best offer. Customers can also name their own price or counter a quote, and workshops can accept it.

One codebase runs on **Android, iOS and the web**.

## How it works

1. **Customer** takes 1-8 photos. The app checks them for blur, darkness and glare.
2. **CV engine** segments the damage (dent, scratch, crack, shattered glass, broken lamp, flat tire), finds which panel it is on, and estimates:
   - size in cm (scaled from the known size of the detected panel)
   - scratch length and paint depth (clear coat, colour coat, or primer/bare metal)
   - dent size (depth is left to the workshop: it cannot be judged reliably from one photo)
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

## Run it (one command)

```bash
./dentbid.sh
```

The script installs everything that is missing, generates secrets in `backend/.env`, builds the web app and starts the server. Then open **http://localhost:8000**.

- The terminal prints the admin login, which is also stored in `backend/.env`.
- Phones on the same Wi-Fi can use the LAN address the script prints.
- You need Python 3.10+ and Node.js 18+.
- `./dentbid.sh --rebuild` forces a fresh web build. `PORT=9000 ./dentbid.sh` changes the port.

With Docker instead (PostgreSQL included):

```bash
docker compose up --build
docker compose logs api | grep "DentBid admin"
```

### Add the AI model

Train on a GPU server, then copy `damage.pt` and `parts.pt` into `ml/weights/` and rerun `./dentbid.sh`:

```bash
bash ml/scripts/gpu_train.sh
```

The script downloads the CarDD dataset and trains both models. See [ml/README.md](ml/README.md). Until the weights are present, workshops quote from the photos alone.

### Mobile app (Android / iOS)

```bash
cd mobile && npx expo start
```

Scan the QR code with Expo Go. For production builds, set `EXPO_PUBLIC_API_URL` and run `npx eas-cli build`.

## Admin panel

Log in with the admin account at http://localhost:8000.

- **Verification:** the queue of workshops waiting for approval, plus platform stats and the AI model status.
- **Workshop review:** shop details, a map link, and the private verification documents. Approve, reject with a reason the shop sees, or suspend.
- **Workshops** and **Users:** search everything, and disable or enable accounts. Disabling signs the user out everywhere.
- Every admin decision is recorded in an audit log (`/api/admin/audit`).

New workshops must be **approved before they can see jobs or send quotes**. Moving the shop more than 1 km or renaming it sends it back for review. Suspending a shop withdraws its open quotes.

## Security

Each of these attacks has an automated test in [`backend/tests/test_admin_security.py`](backend/tests/test_admin_security.py):

| Attack | Defence |
|---|---|
| Forged JWT (`alg=none`, wrong key, expired, tampered) | single pinned algorithm; required claims; `token_version` so tokens can be revoked (logout everywhere, account disabled) |
| Password brute force | 10 attempts per 15 min per IP+email, 50 per IP; bcrypt |
| User enumeration via login | same message, and a dummy bcrypt run when the email does not exist |
| Self-promotion to admin at registration | role is limited to customer or workshop |
| IDOR on requests, quotes, chat, documents | every object is checked against its owner (tested with a second customer and a second workshop) |
| Unverified, suspended or far-away workshops | blocked from the feed, from quoting and from viewing requests |
| Malicious uploads (SVG/HTML, GIF, polyglot JPEG, decompression bomb, oversized) | format allow-list, pixel limit, size limit, then re-encoding to JPEG, which strips EXIF/GPS and hidden payloads |
| Photo URL guessing or sharing | media is served only through HMAC-signed, expiring URLs; verification documents need the owner's or an admin's token |
| Path traversal | every file path is resolved inside its root folder; the web-app fallback never serves files outside `dist/` |
| Huge requests | 130 MB body limit, including chunked uploads |
| Request flooding | rate limit per IP on the whole API |
| Token in WebSocket URL or logs | the socket authenticates with its first message instead |
| SQL injection | ORM parameters, with LIKE wildcards escaped in admin search |
| Clickjacking, MIME sniffing, info leaks | security headers and CSP; `/health` shows no internals; `ENVIRONMENT=production` refuses weak secrets and hides `/docs` |

Before going public, also:
- put the server behind HTTPS (for example Caddy or Nginx);
- set `ENVIRONMENT=production` and `CORS_ORIGINS` to your domain;
- move the rate limiter to Redis if you run more than one API process.

## Tests

```bash
cd ml && pytest -q
cd backend && pytest -q        # includes the attack tests
cd mobile && npx tsc --noEmit
```

## Author

**MIsmail2524**. Licensed under the MIT License.
