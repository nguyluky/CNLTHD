
import http from 'k6/http';
import { check, fail } from 'k6';

const BASE_URL = (
  __ENV.BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

const USERNAME = 'admin@salon.com';
const PASSWORD = 'Admin@123';
const RATE = Number(__ENV.RATE || 1);
const DURATION = __ENV.DURATION || '2m';
const BARBER_ID = __ENV.BARBER_ID || '2';
const TEST_DATE = __ENV.TEST_DATE || '2026-11-05';

export function setup() {

  const response = http.post(
    `${BASE_URL}/auth/login`,
    {
      username: USERNAME,
      password: PASSWORD,
    }
  );

  if (response.status !== 200) {
    console.error(`Login status: ${response.status}`);
    console.error(`Login response: ${response.body}`);
    fail('Login failed');
  }

  const body = response.json();

  return { token: body.access_token };
}

export const options = {
  scenarios: {
    list_barbers: {
      executor: 'constant-arrival-rate',
      exec: 'listBarbers',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },

    list_services: {
      executor: 'constant-arrival-rate',
      exec: 'listServices',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },

    availability: {
      executor: 'constant-arrival-rate',
      exec: 'getAvailability',
      rate: 2,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },

    my_bookings: {
      executor: 'constant-arrival-rate',
      exec: 'getMyBookings',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },

    list_users: {
      executor: 'constant-arrival-rate',
      exec: 'listUsers',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },

    list_barber_schedules: {
      executor: 'constant-arrival-rate',
      exec: 'listBarberSchedules',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },
  },

  thresholds: {
    'http_req_duration{endpoint:barbers}': [
      'p(95)<300',
      'p(99)<700',
    ],
    'http_req_duration{endpoint:services}': [
      'p(95)<300',
      'p(99)<700',
    ],
    'http_req_duration{endpoint:availability}': [
      'p(95)<300',
      'p(99)<700',
    ],
    'http_req_duration{endpoint:my_bookings}': [
      'p(95)<500',
      'p(99)<1000',
    ],
    'http_req_duration{endpoint:users}': [
      'p(95)<500',
      'p(99)<1000',
    ],
    'http_req_duration{endpoint:barber_schedules}': [
      'p(95)<500',
      'p(99)<1000',
    ],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count==0'],
  },
};

function get(path, endpoint, token, requiresAuth = false) {
  const response = http.get(`${BASE_URL}${path}`, {
    headers: requiresAuth
      ? { Authorization: `Bearer ${token}` }
      : {},
    tags: { endpoint },
  });

  check(response, {
    [`${endpoint} returns 200`]: (r) => r.status === 200,
  });
}

export function listUsers(data) {
  get('/admin/users', 'users', data.token, true);
}

export function listBarbers(data) {
  get('/barbers', 'barbers', data.token);
}

export function listBarberSchedules(data) {
  get(`/barber_schedules/${BARBER_ID}/schedules`, 'barber_schedules', data.token, true);
}

export function listServices(data) {
  get('/services', 'services', data.token);
}

export function getAvailability(data) {
  const date = encodeURIComponent(TEST_DATE);

  get(
    `/barbers/${BARBER_ID}/available-slots?booking_date=${date}`,
    'availability',
    data.token
  );
}

export function getMyBookings(data) {
  get('/bookings', 'my_bookings', data.token, true);
}
