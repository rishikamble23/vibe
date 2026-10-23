# SHELFLINE Parameter Reference

This document explains what the important SHELFLINE parameters mean, who is allowed to set them, and how the system should use them.

The main rule is:

> **User input can describe a situation, but server-owned values decide safety.**

For example, a donor may provide when food was cooked, but the server calculates `safe_until` and `deliver_by`.

## 1. Parameter ownership

Every parameter belongs to one of three groups:

| Ownership | Meaning | Examples |
| --- | --- | --- |
| User-provided | Entered by a donor, rider, or shelter | `qty_portions`, `location`, `need` |
| Server-calculated | Computed by the backend and never trusted from the phone | `safe_until`, `deliver_by`, `slack`, `expires_at` |
| System configuration | Set by the project team and used consistently everywhere | `serve_buffer`, `grace_period`, `stall_threshold` |

Clients may display server-calculated values, but they must not overwrite them.

---

## 2. Time parameters

All timestamps must be stored in UTC. The server clock is the source of truth. Phone clocks are never used to decide safety or expiry.

### `now`

**Meaning:** The current time according to the server or simulated clock.

**Reserved for:** All deadline, lease, ETA, and expiry calculations.

**Who sets it:** The clock service only.

**Do not:** Use `datetime.now()` directly inside business logic.

---

### `cooked_at`

**Meaning:** When the donor says the food was cooked or prepared.

**Provided by:** Donor.

**Used for:** Calculating the earliest possible expiry.

**Rules:**

- Must be a valid timestamp.
- Must not be far in the future.
- Must not be changed to extend an active batch's safety window.
- Changes must create an audit event.

---

### `shelf_life_min`

**Meaning:** The maximum number of minutes the item is considered safe under the configured conditions.

**Provided by:** Category configuration, not normally typed manually by a donor.

**Example:** Cooked food may use a conservative category default.

**Rules:**

- Must be positive.
- Must come from an approved category configuration.
- Donors should not be able to increase it freely.

---

### `donor_declared_safe_until`

**Meaning:** An optional safety deadline stated by the donor.

**Provided by:** Donor.

**Used for:** Applying the stricter of the donor declaration and the server calculation.

**Important:** This value can only make the deadline earlier. It can never extend the server-calculated safety window.

---

### `safe_until`

**Meaning:** The final server-calculated time after which the batch must not be treated as safe.

**Calculated as:**

```text
safe_until = min(cooked_at + shelf_life_min, donor_declared_safe_until)
```

If no donor deadline exists, use the category calculation.

**Reserved for:** The hard safety boundary of the batch.

**Who sets it:** Server only.

---

### `serve_buffer`

**Meaning:** Time the shelter needs to distribute the item after arrival.

**Example:** 10–15 minutes for cooked food.

**Used for:** Making sure the item arrives early enough to be served safely.

---

### `deliver_by`

**Meaning:** The latest time the item should arrive at the shelter so the shelter still has time to distribute it.

**Calculated as:**

```text
deliver_by = safe_until - serve_buffer
```

**Reserved for:** Planner safety checks, delivery confirmation, and expiry metrics.

**Who sets it:** Server only.

**Do not confuse with:**

- `safe_until`: final safety limit
- `latest_pickup`: latest safe pickup time
- `expires_at`: lease expiry time

---

### `handover_time`

**Meaning:** Time needed for a handover at a donor or shelter.

**Used for:** ETA and slack calculations.

This must be included for both pickup and delivery handover.

---

### `latest_pickup`

**Meaning:** The latest time the rider may pick up the item and still reach the shelter before `deliver_by`.

**Calculated as:**

```text
latest_pickup = deliver_by - P90(donor_to_shelter) - handover_time
```

**Reserved for:** Pickup cutoffs and lease-extension limits.

---

### `slack`

**Meaning:** The amount of safe time remaining after considering the full route.

**Calculated as:**

```text
slack = deliver_by
        - now
        - P90(rider_to_donor)
        - handover_time
        - P90(donor_to_shelter)
        - handover_time
```

**Interpretation:**

| Slack | Meaning |
| ---: | --- |
| Greater than 0 | Safe margin exists |
| Exactly 0 | Technically feasible, but no margin exists |
| Less than 0 | Unsafe; the assignment must not be created |

---

### `redispatch_reserve`

**Meaning:** Time needed for the next-best rider to reach the donor if the current rider fails.

**Used for:** Preventing a lease from living so long that recovery becomes impossible.

---

### `grace_period`

**Meaning:** Small extra time allowed for rider progress before a soft lease expires.

**Important:** Grace cannot extend beyond the safe recovery cutoff.

---

### `lease_ttl`

**Meaning:** How long a soft lease remains active.

**Calculated as:**

```text
lease_ttl = clamp(
  P90(rider_to_donor) + grace_period,
  min_ttl,
  latest_pickup - now - redispatch_reserve
)
```

If the calculated maximum is less than the configured minimum, the lease must not be created. The system should return an infeasibility reason instead.

---

### `expires_at`

**Meaning:** The exact server time when an offer or soft lease stops being valid.

**Calculated as:**

```text
expires_at = now + lease_ttl
```

**Rules:**

- `now >= expires_at` means expired.
- A late rider action must not revive the lease.
- The reaper must process expired leases automatically.

---

## 3. ETA and location parameters

### `location`

**Meaning:** Latitude and longitude for a donor, rider, shelter, or overflow destination.

**Rules:**

- Latitude must be between `-90` and `90`.
- Longitude must be between `-180` and `180`.
- Reject missing, NaN, infinite, or impossible coordinates.
- Rider location updates must include a server receipt time.

---

### `P50`

**Meaning:** The middle travel-time estimate.

**Used for:** Display and normal progress information.

**Not sufficient for:** Safety decisions.

---

### `P90`

**Meaning:** A pessimistic travel-time estimate used for safety decisions.

**Used for:**

- Candidate filtering
- `slack`
- `latest_pickup`
- Reroute validation
- Multi-stop route validation

The system must always ensure:

```text
P90 >= P50
```

---

### `traffic_multiplier`

**Meaning:** A temporary multiplier used to simulate or represent slower traffic.

**Example:** `3.0` means a severe traffic slowdown.

**Used for:** ETA recalculation and Chaos Console traffic tests.

**Rules:** Must be positive and bounded by a configured maximum.

---

### `progress_ping`

**Meaning:** A rider location update showing where the rider currently is.

**Used for:** Detecting whether the rider is actually moving toward the target.

**A heartbeat alone is not enough.** The distance to the current target must shrink across consecutive pings.

---

### `stall_threshold`

**Meaning:** Number of consecutive non-improving progress pings before a rider becomes `STALLED`.

**Default from plan:** 3 non-shrinking pings.

---

## 4. Batch and lot parameters

### `batch_id`

**Meaning:** Identifier for the original donation or supply submission.

**Reserved for:** Grouping all lots created from the same donation.

---

### `category`

**Meaning:** Type of item being donated.

**Examples:**

- `cooked_meal`
- `raw_ration_kit`
- `infant_formula`
- `cold_chain_medicine`

**Used for:** Selecting shelf life, dependency rules, and safety checks.

---

### `qty_portions`

**Meaning:** Total number of usable portions in the batch.

**Rules:**

- Must be a positive integer.
- Must use one consistent unit.
- Must not become negative after revisions or delivery.

---

### `pickup_window`

**Meaning:** Time range during which a rider may collect the batch.

**Used for:** Planning and feasibility checks.

The pickup window must overlap the period before `latest_pickup`.

---

### `lot_id`

**Meaning:** A smaller, assignable piece of a batch.

**Used for:** Leasing, delivery, rerouting, and partial fulfillment.

The sum of all active lot quantities must never exceed the batch quantity.

---

### `lot.status`

Allowed values:

```text
UNASSIGNED
LEASED
IN_TRANSIT
DELIVERED
EXPIRED
DISCARDED
ABORTED_UNSAFE
```

Only the state machine may change this value.

---

## 5. Rider parameters

### `rider_id`

**Meaning:** Unique identifier for the rider.

---

### `vehicle_capacity_portions`

**Meaning:** Maximum number of portions the rider can carry.

---

### `vehicle_capacity_volume`

**Meaning:** Maximum physical volume the rider can carry.

Capacity must pass both checks:

```text
portions <= vehicle_capacity_portions
volume <= vehicle_capacity_volume
```

---

### `insulated_box`

**Meaning:** Whether the rider has the required temperature-controlled container.

**Required for:** Cold-chain items and any category that requires it.

---

### `reliability_score`

**Meaning:** A rider reliability estimate based on completed work, expiries, and failures.

**Used for:**

- Assignment scoring
- Lease TTL decisions
- Standby selection

It must influence priority, not punish or shame riders.

---

### `rider.status`

Suggested values:

```text
OFFLINE
AVAILABLE
OFFERED
BUSY
STALLED
BREAKDOWN
UNAVAILABLE
```

---

## 6. Lease parameters

### `lease.state`

Normal states:

```text
OFFERED
ACCEPTED
ARRIVED_DONOR
PICKED_UP
NEAR_SHELTER
DELIVERED
```

Failure states:

```text
EXPIRED
RELEASED
REVOKED
REROUTED
ABORTED_UNSAFE
```

The application must reject transitions that are not explicitly allowed.

---

### `last_progress_at`

**Meaning:** Last time the rider sent meaningful progress.

This should not be refreshed by a heartbeat that does not reduce distance to the target.

---

### `fallbacks`

**Meaning:** Ordered alternative destinations or riders that can be used if the primary plan fails.

Fallbacks are not permanent promises. Each one must be rechecked before use.

Every in-transit lease must have either:

- At least one valid fallback, or
- An explicit `NONE_AVAILABLE` result with a reason

---

### `idempotency_key`

**Meaning:** A client-provided key that makes retries safe.

**Used for:** Every mutating API request.

The server should scope it by actor and endpoint and reject reuse with a different request body.

---

## 7. Shelter parameters

### `need`

**Meaning:** Total number of portions the shelter currently needs.

---

### `received_confirmed`

**Meaning:** Portions the shelter has confirmed receiving.

---

### `committed_in_transit`

**Meaning:** Portions already promised to the shelter by active leases but not yet confirmed as delivered.

---

### `available`

**Calculated as:**

```text
available = need - received_confirmed - committed_in_transit
```

For display, negative values should be shown as overcommitted, but new reservations must not increase the overcommit unless the shelter explicitly allows soft overbooking.

---

### `intake_open`

**Meaning:** Whether the shelter can currently receive deliveries.

If false, it must not be selected as a new destination.

---

### `capabilities`

Examples:

```text
water
fuel
fridge
heating_or_kettle
serving_capacity
```

Capabilities are checked against item rules.

---

### `capabilities_verified_at`

**Meaning:** Last time the shelter confirmed its capabilities.

When the verification is too old, the capability becomes `UNKNOWN`.

Recommended safety rule:

```text
TRUE    → allowed
FALSE   → blocked
UNKNOWN → blocked until reconfirmed
```

---

### `accepts_diet_tags`

**Meaning:** Diet categories accepted by the shelter.

Examples:

```text
veg
non_veg
halal
jain
```

The matching behavior must be explicitly defined. Do not silently treat missing diet information as safe.

---

## 8. Item and compatibility parameters

### `requires`

**Meaning:** Shelter capabilities required by an item.

Example:

```yaml
item: raw_ration_kit
requires:
  - cooking_fuel
  - clean_water
```

---

### `rider_requires`

**Meaning:** Rider equipment required by an item.

Example:

```yaml
item: cold_chain_medicine
rider_requires:
  - insulated_box
```

---

### `max_ambient_minutes`

**Meaning:** Maximum time an item may remain outside its required temperature conditions.

The system must account for all relevant time, including:

- Waiting before pickup
- Pickup handover
- Travel
- Waiting at the shelter
- Delivery handover

---

### `diet_must_match`

**Meaning:** Diet labels that must be compatible between the item and shelter.

---

## 9. Planner parameters

### `urgency_weight`

**Meaning:** How strongly the planner prioritizes a shelter’s urgency.

---

### `detour_penalty`

**Meaning:** How much extra route distance reduces an assignment’s score.

---

### `late_penalty`

**Meaning:** Penalty for an assignment with a high late-delivery probability.

Unsafe assignments should be rejected by the Safety Gate, not merely given a bad score.

---

### `reliability_penalty`

**Meaning:** How much a rider’s low reliability reduces their assignment score.

---

### `hysteresis_threshold`

**Meaning:** Minimum improvement required before rerouting a rider who is already moving.

This prevents constant route changes.

---

### `planner_time_limit_ms`

**Meaning:** Maximum time allowed for the always-available greedy planner.

**Target from the build plan:** 200 ms.

If the optional optimizer times out, the system must keep the greedy plan.

---

## 10. Event parameters

Events are permanent records of what happened.

Each event should contain:

```text
event_id
event_type
actor_id
payload
idempotency_key
schema_version
```

Important event types include:

```text
BATCH_CREATED
BATCH_REVISED
LOT_CREATED
LEASE_OFFERED
LEASE_ACCEPTED
LEASE_DECLINED
RIDER_PING
RIDER_MILESTONE
LEASE_STALLED
LEASE_EXPIRED
LEASE_RELEASED
PICKUP_CONFIRMED
DELIVERY_CONFIRMED
DEMAND_CHANGED
SHELTER_CLOSED
WALK_IN_RECEIVED
CAPABILITY_CHANGED
REROUTE_PROPOSED
REROUTE_ACKED
UNSAFE_REPORTED
LOT_EXPIRED
LOT_DISCARDED
PLAN_COMMITTED
CHAOS_INJECTED
```

Events must be replayable. Replaying the event log should produce the same state as the live database.

---

## 11. Important calculated metrics

### `portions_delivered_safely`

Number of portions confirmed delivered before the safety deadline.

### `portions_wasted`

Number of portions not delivered safely.

Waste should include a reason:

```text
EXPIRED
UNSAFE
INFEASIBLE
DISCARD_REQUIRED
```

### `spoilage_violations`

Number of deliveries completed after `deliver_by` without being explicitly recorded as a safety exception.

Target:

```text
0
```

### `ghost_lease_rate`

Percentage of soft leases that expire because the rider failed to make sufficient progress.

### `median_time_to_reassign`

Median time from lease failure detection to a valid replacement assignment.

### `reroute_decision_time`

Time from a disruption event to a new route decision.

Target from the plan: under one second of server time.

### `reroute_acknowledgment_time`

Time from sending a new route to rider acknowledgment.

Target from the plan: under 60 seconds.

---

## 12. Parameters that must never be trusted from the client

The backend must calculate or verify these values:

```text
now
safe_until
slack
latest_pickup
lease_ttl
expires_at
P50
P90
lease state
lot state
shelter availability
received quantities
committed quantities
reliability score
spoilage metrics
```

The client may request an action, but the server must decide whether the action is valid.

## 13. Minimum validation rules

Reject requests when:

- Quantity is zero, negative, or not an integer.
- Coordinates are invalid.
- A timestamp is impossible or too far in the future.
- A category is unknown.
- A lease transition is not allowed.
- The lot is expired, unsafe, or discarded.
- The shelter is closed.
- The shelter lacks required capabilities.
- The rider lacks capacity or required equipment.
- The P90 route arrives after `deliver_by`.
- An idempotency key is reused with a different payload.
- A delivery would make the ledger invalid.

## 14. Simple example

```text
Food quantity: 180 portions
Cooked at: 20:00
Shelf life: 75 minutes
Serving buffer: 10 minutes

safe_until = 21:15
deliver_by = 21:05
```

If the route requires:

```text
Rider to donor: 12 minutes P90
Pickup handover: 5 minutes
Donor to shelter: 25 minutes P90
Delivery handover: 10 minutes
```

Then the route consumes:

```text
12 + 5 + 25 + 10 = 52 minutes
```

If the current time is 20:10:

```text
slack = 21:05 - 20:10 - 52 minutes
slack = 3 minutes
```

The route is technically feasible, but very risky. A planner may reject it if the configured minimum safety margin is greater than three minutes.
