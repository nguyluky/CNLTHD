
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = (
  __ENV.BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

const USERNAME = __ENV.K6_USERNAME || 'admin@salon.com';
const PASSWORD = __ENV.K6_PASSWORD || 'Admin@123';
const RATE = Number(__ENV.RATE || 1);
const DURATION = __ENV.DURATION || '2m';

export const options = {
  scenarios: {
    login: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 2,
      maxVUs: 10,
    },
  },

  thresholds: {
    http_req_duration: [
      'p(95)<150',
      'p(99)<300',
    ],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count==0'],
  },
};

export default function () {
  const response = http.post(
    `${BASE_URL}/auth/login`,
    {
      username: USERNAME,
      password: PASSWORD,
    }
  );

  check(response, {
    'login returns success': (r) => r.status === 200,
  });
}
