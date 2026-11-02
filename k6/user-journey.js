import http from 'k6/http';
import { check, fail } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = (
  __ENV.BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

const EMAIL = "customer001@salon.test";
const PASSWORD = "Customer@123";

const RATE = Number(__ENV.RATE || 1);
const DURATION = __ENV.DURATION || '2m';
const PRE_ALLOCATED_VUS = Number(__ENV.PRE_ALLOCATED_VUS || 5);
const MAX_VUS = Number(__ENV.MAX_VUS || 20);

const BARBER_ID = __ENV.BARBER_ID
  ? Number(__ENV.BARBER_ID)
  : null;

const SERVICE_IDS = (__ENV.SERVICE_IDS || '')
  .split(',')
  .map((id) => id.trim())
  .filter(Boolean)
  .map(Number);

const BOOKING_DATE =
  __ENV.BOOKING_DATE ||
  new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);

// Measures the duration of a complete successful user journey.
const journeyDuration = new Trend('journey_duration', true);

if (!EMAIL || !PASSWORD) {
  throw new Error('LOGIN_EMAIL and LOGIN_PASSWORD are required');
}

if (!Number.isInteger(RATE) || RATE < 1) {
  throw new Error('RATE must be a positive integer');
}

if (
  !Number.isInteger(PRE_ALLOCATED_VUS) ||
  !Number.isInteger(MAX_VUS) ||
  PRE_ALLOCATED_VUS < 1 ||
  MAX_VUS < PRE_ALLOCATED_VUS
) {
  throw new Error('Invalid VU configuration');
}

if (BARBER_ID !== null && (!Number.isInteger(BARBER_ID) || BARBER_ID < 1)) {
  throw new Error('BARBER_ID must be a positive integer');
}

if (SERVICE_IDS.some((id) => !Number.isInteger(id) || id < 1)) {
  throw new Error('SERVICE_IDS must contain positive integer IDs');
}

if (!/^\d{4}-\d{2}-\d{2}$/.test(BOOKING_DATE)) {
  throw new Error('BOOKING_DATE must use YYYY-MM-DD format');
}

export const options = {
  scenarios: {
    customer_journey: {
      executor: 'constant-arrival-rate',
      exec: 'userJourney',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
      gracefulStop: '30s',
    },
  },

  thresholds: {
    checks: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
    dropped_iterations: ['count==0'],

    http_req_duration: [
      'p(95)<800',
      'p(99)<1500',
    ],

    journey_duration: [
      'p(95)<5000',
      'p(99)<10000',
    ],
  },
};

function requireStatus(response, expectedStatus, step) {
  const passed = check(response, {
    [`${step}: HTTP ${expectedStatus}`]: (r) =>
      r.status === expectedStatus,
  });

  if (!passed) {
    console.error(
      `[${step}] Expected ${expectedStatus}, got ${response.status}`
    );
    console.error(`[${step}] Response: ${response.body}`);

    fail(`${step} failed`);
  }
}

function parseJson(response, step) {
  try {
    return response.json();
  } catch (error) {
    console.error(`[${step}] Invalid JSON response: ${error}`);
    fail(`${step} returned invalid JSON`);
  }
}

function chooseRandom(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function requireNonEmptyArray(items, step) {
  const passed = check(items, {
    [`${step}: has available items`]: (value) =>
      Array.isArray(value) && value.length > 0,
  });

  if (!passed) {
    fail(`${step}: no available items`);
  }
}

export function userJourney() {
  const journeyStartedAt = Date.now();

  // =========================================================
  // STEP 1: Login
  // POST /auth/login
  // =========================================================

  const loginResponse = http.post(
    `${BASE_URL}/auth/login`,
    {
      username: EMAIL,
      password: PASSWORD,
    },
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      tags: {
        endpoint: 'login',
      },
    }
  );

  requireStatus(loginResponse, 200, 'Login');

  const loginData = parseJson(loginResponse, 'Login');

  const hasToken = check(loginData, {
    'Login: access_token exists': (data) =>
      typeof data.access_token === 'string' &&
      data.access_token.length > 0,
  });

  if (!hasToken) {
    fail('Login response does not contain access_token');
  }

  const authHeaders = {
    Authorization: `Bearer ${loginData.access_token}`,
  };

  // =========================================================
  // STEP 2: Get service list
  // GET /services
  // =========================================================

  const servicesResponse = http.get(
    `${BASE_URL}/services?page=1&limit=100`,
    {
      tags: {
        endpoint: 'services',
      },
    }
  );

  requireStatus(servicesResponse, 200, 'Get services');

  const servicesData = parseJson(
    servicesResponse,
    'Get services'
  );

  requireNonEmptyArray(servicesData.items, 'Services');

  // Use SERVICE_IDS when provided.
  // Otherwise, randomly choose one service.
  let selectedServices;

  if (SERVICE_IDS.length > 0) {
    const serviceMap = new Map(
      servicesData.items.map((service) => [
        Number(service.id),
        service,
      ])
    );

    selectedServices = SERVICE_IDS.map((id) =>
      serviceMap.get(id)
    );

    if (selectedServices.some((service) => !service)) {
      fail('One or more SERVICE_IDS were not found in GET /services');
    }
  } else {
    selectedServices = [chooseRandom(servicesData.items)];
  }

  const selectedServiceIds = selectedServices.map(
    (service) => Number(service.id)
  );

  const totalServiceDuration = selectedServices.reduce(
    (total, service) => total + Number(service.duration_minutes),
    0
  );

  if (!Number.isInteger(totalServiceDuration) || totalServiceDuration <= 0) {
    fail('Selected services have an invalid duration');
  }

  // =========================================================
  // STEP 3: Get barber list
  // GET /barbers
  // =========================================================

  const barbersResponse = http.get(
    `${BASE_URL}/barbers?page=1&limit=100`,
    {
      tags: {
        endpoint: 'barbers',
      },
    }
  );

  requireStatus(barbersResponse, 200, 'Get barbers');

  const barbersData = parseJson(
    barbersResponse,
    'Get barbers'
  );

  requireNonEmptyArray(barbersData.items, 'Barbers');

  const activeBarbers = barbersData.items.filter(
    (barber) => barber.is_active === true
  );

  requireNonEmptyArray(activeBarbers, 'Active barbers');

  let selectedBarber;

  if (BARBER_ID !== null) {
    selectedBarber = activeBarbers.find(
      (barber) => Number(barber.id) === BARBER_ID
    );

    if (!selectedBarber) {
      fail(`Configured barber ${BARBER_ID} was not found or is inactive`);
    }
  } else {
    selectedBarber = chooseRandom(activeBarbers);
  }

  // =========================================================
  // STEP 4: Get available time slots
  // GET /barbers/{barber_id}/available-slots
  // =========================================================

  const availabilityUrl =
    `${BASE_URL}/barbers/${selectedBarber.id}/available-slots` +
    `?booking_date=${encodeURIComponent(BOOKING_DATE)}` +
    `&slot_duration=${totalServiceDuration}`;

  const availabilityResponse = http.get(
    availabilityUrl,
    {
      tags: {
        endpoint: 'availability',
      },
    }
  );

  requireStatus(
    availabilityResponse,
    200,
    'Get availability'
  );

  const availabilityData = parseJson(
    availabilityResponse,
    'Get availability'
  );

  requireNonEmptyArray(
    availabilityData.available_slots,
    'Available slots'
  );

  // Choose one available slot.
  const selectedSlot = chooseRandom(
    availabilityData.available_slots
  );

  // =========================================================
  // STEP 5: Create booking
  // POST /bookings
  // =========================================================

  const bookingPayload = {
    barber_id: Number(selectedBarber.id),
    booking_date: BOOKING_DATE,
    start_time: selectedSlot.start_time,
    service_ids: selectedServiceIds,
  };

  const createBookingResponse = http.post(
    `${BASE_URL}/bookings`,
    JSON.stringify(bookingPayload),
    {
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json',
      },
      tags: {
        endpoint: 'booking_create',
      },
    }
  );

  requireStatus(
    createBookingResponse,
    201,
    'Create booking'
  );

  const createdBooking = parseJson(
    createBookingResponse,
    'Create booking'
  );

  const hasBookingId = check(createdBooking, {
    'Create booking: booking ID exists': (booking) =>
      Number.isInteger(Number(booking.id)),
  });

  if (!hasBookingId) {
    fail('Create booking response does not contain a valid booking ID');
  }

  // =========================================================
  // STEP 6: Get booking detail
  // GET /bookings/{booking_id}
  // =========================================================

  const bookingDetailResponse = http.get(
    `${BASE_URL}/bookings/${createdBooking.id}`,
    {
      headers: authHeaders,
      tags: {
        endpoint: 'booking_detail',
      },
    }
  );

  requireStatus(
    bookingDetailResponse,
    200,
    'Get booking detail'
  );

  const bookingDetail = parseJson(
    bookingDetailResponse,
    'Get booking detail'
  );

  const bookingMatches = check(bookingDetail, {
    'Booking detail: ID matches created booking': (booking) =>
      booking.id === createdBooking.id,

    'Booking detail: barber ID matches': (booking) =>
      booking.barber_id === bookingPayload.barber_id,

    'Booking detail: booking date matches': (booking) =>
      booking.booking_date === bookingPayload.booking_date,

    'Booking detail: start time matches': (booking) =>
      booking.start_time === bookingPayload.start_time,

    'Booking detail: customer ID exists': (booking) =>
      Number.isInteger(Number(booking.customer_id)),
  });

  if (!bookingMatches) {
    fail('Retrieved booking detail does not match the created booking');
  }

  // Record total time for a successful journey.
  journeyDuration.add(Date.now() - journeyStartedAt);
}