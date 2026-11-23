# Property revenue dashboard

Two clients called about the new revenue dashboard. Sunset said March did not match their books. Ocean said a refresh sometimes showed another company's numbers. Finance also kept finding totals that were off by a cent or two.

There were three separate bugs. The notes below are what was wrong, why, and what changed.

Run it with:

```bash
docker-compose up --build
```

App: http://localhost:3000
API docs: http://localhost:8000/docs

Sunset: `sunset@propertyflow.com` / `client_a_2024`
Ocean: `ocean@propertyflow.com` / `client_b_2024`

## Ocean was seeing Sunset's revenue

Both companies have a property with the id `prop-001`. Sunset's is Beach House Alpha. Ocean's is Mountain Lodge Beta. The database allows that. The primary key is the property id plus the company, not the id on its own.

The cache did not. The Redis key was only `revenue:prop-001`, and it lived for 5 minutes. Whoever opened that property first left their total in the cache. The next person, even from the other company, got those numbers back on refresh. That is why it only happened sometimes. After 5 minutes the key expired and the real query ran again.

The property dropdown made it easier to hit. It was a hardcoded list of every property, so each company could open the other's.

The key now includes the company, the property, and the month:

```python
cache_key = f"revenue:{tenant_id}:{property_id}:{year}:{month:02d}"
```

That lives in `backend/app/services/cache.py`. Before a cached value is used, the code also checks that the company and property on it still match the request.

The dropdown no longer lists both companies. `list_tenant_properties` in `backend/app/services/reservations.py` loads only the logged-in company's rows, and the dashboard calls that.

There was a second way both clients got the same numbers. The old database pool looked for Supabase settings that are not set in this project, so the query failed and fell back to one shared set of mock totals. Revenue is now read from the local Postgres database (`DATABASE_URL`).

Check: log in as Sunset and open Beach House. March is **USD 2,250.00**. Log out, log in as Ocean, and open Mountain Lodge. Same id, `prop-001`, but the total is **USD 0.00**. Ocean's list is only Lakeside Cottage, Mountain Lodge, and Urban Loft.

## Sunset's March total was short by $1,250

Beach House is in Paris. One booking checks in at 29 February 2024, 23:30 UTC. Paris is an hour ahead in February, so locally that is 1 March, 00:30. Sunset counts it in March. The old month cutoff was plain UTC, so that $1,250 stay was left in February. March showed $1,000 instead of $2,250.

The month is now the property's own month. The check-in is converted with `AT TIME ZONE` before it is compared with the start and end of the month. That query is in `calculate_monthly_revenue` in `backend/app/services/reservations.py`.

Beach House for March 2024 is **USD 2,250.00** from **4 bookings**: the three smaller stays plus the $1,250 one.

## Totals were off by a few cents

Bookings are stored with 3 decimal places, for example `333.333`, `333.333`, and `333.334`. Added exactly, those are `1000.000`. Rounded to cents one booking at a time, they are `999.99`. That missing cent is what finance was seeing, and it showed up on other properties the same way.

The API was also turning the total into a normal JSON number. Those are binary floats, and cents do not always survive the trip to the browser. The page then did `Math.round(n * 100) / 100`, which can move the value by another cent.

The bookings are added as decimals, the total is rounded to cents once, and the API sends it as text, like `"2250.00"`. The page prints that text. It does not parse it back into a float. See `_money` in `reservations.py`, the summary response in `backend/app/api/v1/dashboard.py`, and `formatMoney` in `frontend/src/components/RevenueSummary.tsx`.

Lakeside Cottage shows **USD 1,776.50**. Urban Loft shows **USD 3,256.00**.
