# [Project Name]

## Features

### Core dispatch
- **Batches** with quantity, item type, and expiry window
- **Rider registration:** capacity, location, availability
- **Shelter registration:** demand, open/full/closed status, and a profile of what the site has or lacks (clean water, cooking fuel, refrigeration)
- **Time-aware matching:** a rider is assigned only if pickup plus travel fits before expiry, within rider capacity and shelter demand
- **Batch splitting** across multiple riders and multiple shelters
- **Live dashboard** of batches, riders, and shelters

### Spoilage-aware timing
- **Latest safe pickup time** = expiry − travel time − handover buffer
- Live **viability countdown** on every batch

### Ghost-reservation prevention
- **Claims are leases, not locks:** unconfirmed claims release automatically
- **Adaptive confirm window:** shrinks as expiry nears
- **Staged progress:** claimed → confirmed with ETA → picked up → delivered
- **Automatic background heartbeats:** riders never reply to anything while riding
- **Staged escalation:** at risk → SMS/call → release and reassign
- **ETA check:** a batch is released if the rider can no longer make the latest safe pickup time
- **Warm backup rider** pre-alerted for instant reassignment
- **Atomic claims:** two simultaneous claims produce exactly one winner
- **Rider reliability score** (completed deliveries vs. no-shows), used for urgent batches only

### Changing conditions
- **In-transit commitment:** food on its way counts as promised to a shelter
  `open demand = stated demand − delivered − in transit`
- **Pre-computed fallback shelters:** a ranked list calculated before departure, so rerouting is instant when a shelter closes
- **Shelter reconfirmation** prompts and a one-tap "citizen drop-off received" button

### Harm prevention
- **Item requirements** (for example, infant formula needs clean water, raw ration kits need cooking fuel)
- **Hard blocks** for incompatible item and shelter pairs, with a visible reason
- **Warnings** for stale shelter profiles
- Rules re-checked at assignment and on every reroute

### Last resort
- If nothing can be delivered safely in time, the system **flags it early** and redirects it (animal feed, compost)

### Triage
- Infant formula and medicine outrank cooked food (emergency situations only)

### Offline tolerance and SMS
- Assignment, route, and fallback list stored on the rider's phone
- Offline actions queued with timestamp and unique ID, synced on reconnect without double-counting
- SMS fallback with short commands for riders and shelter staff

### Map
- Donors, shelters, and riders on a live map
- Rider routes with the fallback shelter shown
- Batches colored by urgency, shelters by status

### Demo and transparency
- **Chaos panel:** kill a rider, close a shelter, fast-forward time
- **Decision log:** plain-language explanation of every assignment and reroute
- **Impact metrics:** meals saved and waste avoided

### Privacy
- Riders tracked only during an active delivery, with consent
- Donors and shelters see name, ETA, and status only
- Detailed location history deleted after delivery

---

## Implementation Details

Build-level spec for each feature. Assumes a MERN stack. Tunable numbers are examples.

### 0. Foundations (build first)

**Simulated clock.** Every time check uses `clock.now()`, never `Date.now()`. The clock has an offset and a speed multiplier, which is what makes the chaos panel's fast-forward work.

**Collections**
- **Batch:** donorId, items `[{type, qty}]`, `remainingQty` (unassigned), cookedAt, expiryAt, status (`open`, `partial`, `assigned`, `completed`, `expired`, `last_resort`), urgent flag
- **Assignment:** batchId, riderId, shelterId, qty, status, claimDeadlineAt, latestSafePickupAt, fallbackShelterIds, lastHeartbeatAt, standbyRiderIds
- **Rider:** location, capacity, status (`available`, `busy`, `offline`), completed, noShows, consent
- **Shelter:** location, status, per item type `{demand, received, committed}`, profile `{cleanWater, cookingFuel, refrigeration}`, lastConfirmedAt
- **ItemRule:** type → requirements, priority tier
- **DecisionLog:** timestamp, event, inputs, chosen option, rejected options with reasons

**Real-time updates:** Socket.IO to the dashboard.

**Scheduler:** one `setInterval` tick every 5 to 10 seconds that scans stored deadline fields. This survives restarts, unlike scattered `setTimeout` calls.

### 1. Core dispatch

**Batches and registration.** Validate that expiry is in the future and qty > 0. Riders and shelters are plain CRUD plus status updates.

**Matching engine** (greedy is enough):
1. Take an open batch's `remainingQty`.
2. For each candidate (rider, shelter), check:
   - Rider is available, with capacity > 0.
   - Shelter is open, compatible (section 5), and `openDemand > 0`.
   - Time fits: `now + t(rider→donor) + loading + t(donor→shelter) + buffer ≤ expiry`.
3. Pick the pair with the largest safety margin (expiry minus arrival). Break ties by shorter trip.
4. Chunk = `min(rider capacity, remainingQty, shelter openDemand)`. Create the assignment and reserve atomically (section 3).
5. Repeat until nothing remains, or no feasible pair exists, which triggers last resort.

**Splitting** is the same loop producing several assignments. If one fails, its qty goes back to `remainingQty` (atomic `$inc`) and matching re-runs with the **original expiry**.

### 2. Spoilage timing

```
latestSafePickupAt = expiry − t(donor→shelter) − handoverBuffer
countdown = latestSafePickupAt − now
```

Recompute when the shelter changes or the ETA shifts. Colors: green above 30 min, amber 10 to 30, red below 10 (example thresholds).

### 3. Ghost-reservation prevention

**Lease states:** `claimed → confirmed → picked_up → delivered`, with `released` possible from any early state. Each state has a deadline field.

**Adaptive window:**
```
confirmWindow = clamp(0.15 × timeToLatestSafePickup, 2 min, 10 min)
```
At 20 minutes left, that gives 3 minutes.

**Heartbeat.** The rider client sends `POST /heartbeat {lat, lng}` every ~30 s, only during an active assignment. The server stores `lastHeartbeatAt`.

**Escalation** (example values), each tick:
- Silence > 60 s → `at_risk` (no other change).
- Silence > 3 min → SMS or call.
- Silence > `min(5 min, 0.3 × remaining margin)` → release.
- Independently, if `now + ETA from last known position > latestSafePickupAt` → release, even if the rider is responsive.

**Warm backup.** On `at_risk`, run the matching engine excluding this rider, store the top 1 to 2 as `standbyRiderIds`, and notify them. On release, promote a standby who accepts; otherwise rerun matching.

**Release steps:** mark `released`, return qty to the batch, release the shelter commitment, increment `noShows` (if past confirmation), write a log entry.

**Atomic claims:**
```js
Batch.findOneAndUpdate(
  { _id, remainingQty: { $gte: qty } },
  { $inc: { remainingQty: -qty } })
```
A `null` result means someone else won. Reserving batch qty and shelter commitment touches two documents, so use a transaction (needs a replica set; Atlas free tier has one) or reserve-then-compensate: if the second reserve fails, undo the first.

**Reliability score:** `(completed + 1) / (completed + noShows + 2)`, so new riders start at 0.5. For urgent batches, filter out riders below a threshold and sort by score. It is also used to pick standby riders.

### 4. Changing conditions

**In-transit commitment.** `openDemand = demand − received − committed`.
- Reserve `committed` when the assignment is created.
- Move it to `received` on delivery.
- Release it on release, reroute, or failure.

**Citizen drop-off.** The shelter taps a button and enters a qty, which reduces demand. If `openDemand < 0`, the shelter is over-committed. Reroute the assignments with the least progress until it balances.

**Fallback shelters.** At assignment time, build a ranked list: open, compatible, `openDemand > 0`, reachable before expiry. Rank by margin, then distance. Store the IDs.

**Reroute:**
1. Take the first fallback and re-validate it (it may have changed), reserving atomically.
2. If it can only take part of the cargo, split across two fallbacks.
3. If none are valid, recompute from the rider's current position.
4. If still none, last resort.

**Reconfirmation.** A job flags shelters with a stale `lastConfirmedAt` (more than N hours) and prompts them. Stale means a warning, not exclusion.

### 5. Harm prevention

```js
checkCompatibility(item, shelter) → { ok, hardBlocks: [], warnings: [] }
```

- **Hard block:** an item requirement (for example `cleanWater`) is false in the shelter's profile.
- **Warning:** the profile is stale.
- Call it in matching, fallback building, and reroutes.
- **Trigger on change:** when a shelter's profile updates, re-check all its in-transit assignments and reroute failures.
- Always return human-readable reasons for the log.

### 6. Last resort

**Triggers**
- Matching finds no feasible pair for the remaining qty.
- The periodic viability scan finds a batch whose margin is nearly gone.

**Action:** flag the batch early to the admin and set `status: last_resort`. Show the redirect options (animal feed, compost partners) and let the admin or donor confirm one. Count these as *diverted*, separate from *wasted*, in the metrics.

### 7. Triage (emergency only)

Add a global `emergencyMode` flag toggled by the admin. Each ItemRule has a `tier` (high for infant formula and medicine, normal for the rest). When the flag is on, sort the matching queue by tier first, then by earliest deadline. When off, sort by deadline only.

### 8. Offline tolerance and SMS

**Rider PWA**
- Cache the assignment, route, and fallback list in IndexedDB.
- Queue actions as `{opId (uuid), type, assignmentId, deviceTs}`.
- On reconnect, `POST /sync` sends the batch.
- The server keeps a unique index on `opId`, so duplicates are ignored.

**Conflicts.** If a late "delivered" arrives for an assignment already released or reassigned, mark it `late_report`, check shelter confirmation, and flag the admin. The shelter's confirmation is the source of truth for `received`, so meals are never double-counted. Deadlines use server time; device time is for ordering only.

**SMS.** Write an `SmsProvider` interface with `send(to, msg)` and an inbound `POST /sms/inbound`. The prototype implementation is a mock phone panel in the UI. Commands:
- `1` = confirm
- `D` = delivered
- `FULL` = shelter full

Look up the sender by phone number, then act on their active assignment.

**Offline planning.** An offline rider's status is `unknown`. Project the ETA from the last known position with a pessimistic factor, and use the normal staged escalation.

### 9. Map

**Travel service:**
```js
getTravel(from, to) → { minutes, km }
```
- **v1:** haversine distance ÷ average speed (about 20 km/h), × 1.3 for road detours, × 1.25 as a pessimistic buffer.
- **v2:** OSRM or OpenRouteService, behind the same function.

**Display (react-leaflet):** markers for donors, shelters, and riders; polylines for routes; the fallback in a lighter line; batches colored by urgency; shelters colored by status.

**Rider simulator:** moves each rider along the route at speed × clock multiplier and emits heartbeats. Killing a rider just stops its heartbeats.

### 10. Demo and transparency

**Chaos panel endpoints**
- `kill-rider/:id` (stops heartbeats)
- `close-shelter/:id`
- `citizen-dropoff/:id`
- `advance-clock`

**Decision log.** Write the entry at the moment of the decision, as structured data plus a rendered sentence, for example "Rider B chosen: margin 12 min; Rider A rejected: capacity 20 < 40." Reconstructing the reason afterwards is hard.

**Impact metrics:** meals delivered, diverted, and expired; riders recovered after a ghost; average safety margin.

### 11. Privacy

- Accept heartbeats only when the rider has an active assignment and has given consent.
- Role-based response shaping: donor and shelter APIs never return lat/lng.
- Store the location trail with a **Mongo TTL index** so it auto-deletes after completion. Keep only counts for the reliability score.

### Suggested build order

1. Clock, collections, travel service
2. Compatibility rules
3. Matching, splitting, atomic reserve
4. Lease, heartbeat, scheduler
5. In-transit commitment, fallbacks, reroute
6. Last resort
7. Dashboard, map, log, chaos panel
8. Offline sync and SMS mock
9. Emergency mode and privacy
