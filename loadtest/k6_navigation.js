// Scenario A — 100 concurrent authenticated users doing read/navigation traffic.
//
//   k6 run -e BASE_URL=http://127.0.0.1:8200 loadtest/k6_navigation.js
//
// Deliberately read-only: a capacity baseline must not corrupt learning records.
// The point of the run is the SLO in docs/ARCH.md §16 — an ordinary authenticated
// GET is under one second at p95 with no provider involvement.

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8200";
const USERS = (__ENV.USERS || "student1,student2,student3").split(",");
const PASSWORD = __ENV.PASSWORD || "student123";
const TEACHER_TOKEN = __ENV.TEACHER_TOKEN || "";
const STUDENT_IDS = (__ENV.STUDENT_IDS || "1,2,3").split(",");
// A browser session authenticates once and then navigates. Set
// LOGIN_EACH_ITERATION=1 to model the opposite (and to price bcrypt hashing into
// the capacity number on purpose).
const LOGIN_EACH_ITERATION = __ENV.LOGIN_EACH_ITERATION === "1";

export const readLatency = new Trend("clinpath_read_latency", true);
export const loginLatency = new Trend("clinpath_login_latency", true);

let cachedToken = null;

export const options = {
  scenarios: {
    navigation: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: Number(__ENV.TARGET_VUS || 100) },
        { duration: __ENV.HOLD || "2m", target: Number(__ENV.TARGET_VUS || 100) },
        { duration: "15s", target: 0 },
      ],
      gracefulRampDown: "15s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{expected:read}": ["p(95)<1000"],
  },
};

function login(user) {
  const started = Date.now();
  const response = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: user, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" }, tags: { expected: "auth" } },
  );
  loginLatency.add(Date.now() - started);
  const cookie = response.cookies.access_token;
  if (!cookie || !cookie.length) {
    return null;
  }
  return cookie[0].value;
}

export default function () {
  const user = USERS[(__VU + __ITER) % USERS.length];
  if (!cachedToken || LOGIN_EACH_ITERATION) {
    cachedToken = login(user);
  }
  const token = cachedToken;
  if (!token) {
    check(null, { "login succeeded": () => false });
    return;
  }
  const headers = { Cookie: `access_token=${token}` };
  const reads = [
    "/api/student/dashboard",
    "/api/student/pathway",
    "/api/student/competency",
    "/api/student/knowledge-progress",
    "/api/knowledge",
    "/api/cases",
    "/api/cases/1",
    "/api/sp-cases",
    "/api/skills",
    "/api/guidelines",
  ];

  for (const path of reads) {
    const response = http.get(`${BASE_URL}${path}`, { headers, tags: { expected: "read" } });
    readLatency.add(response.timings.duration);
    check(response, { "read returned 200": (r) => r.status === 200 });
    sleep(0.2);
  }

  // Teacher read-only views are part of realistic pilot traffic.
  if (TEACHER_TOKEN) {
    const teacherHeaders = { Cookie: `access_token=${TEACHER_TOKEN}` };
    const studentId = STUDENT_IDS[__ITER % STUDENT_IDS.length];
    const teacherReads = ["/api/teacher/dashboard", `/api/teacher/students/${studentId}/learning-profile`];
    for (const path of teacherReads) {
      const response = http.get(`${BASE_URL}${path}`, {
        headers: teacherHeaders,
        tags: { expected: "read" },
      });
      readLatency.add(response.timings.duration);
      check(response, { "teacher read returned 200": (r) => r.status === 200 });
      sleep(0.2);
    }
  }

  sleep(1);
}
