// Scenario B — ordinary navigation while AI work is in flight.
//
//   k6 run -e BASE_URL=http://127.0.0.1:8200 -e AI_VUS=10 -e SCORING_VUS=5 \
//          loadtest/k6_mixed_ai.js
//
// The provider behind this run is loadtest/mock_provider.py, so the numbers are
// ClinPath's capacity, not DeepSeek's. What must hold: navigation stays
// responsive, AI failures stay isolated, and no request turns into a 5xx.

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8200";
const USERS = (__ENV.USERS || "student1,student2,student3").split(",");
const PASSWORD = __ENV.PASSWORD || "student123";
const AI_VUS = Number(__ENV.AI_VUS || 10);
const SCORING_VUS = Number(__ENV.SCORING_VUS || 5);
const ANSWER = __ENV.ANSWER || "发热、皮疹、ANA阳性、蛋白尿，需要评估器官受累与感染筛查。";

export const readLatency = new Trend("clinpath_read_latency", true);
export const aiLatency = new Trend("clinpath_ai_latency", true);

let cachedToken = null;

export const options = {
  scenarios: {
    navigation: {
      executor: "constant-vus",
      vus: Number(__ENV.NAV_VUS || 100),
      duration: __ENV.DURATION || "2m",
      exec: "navigate",
      tags: { workload: "navigation" },
    },
    tutor: {
      executor: "constant-vus",
      vus: AI_VUS,
      duration: __ENV.DURATION || "2m",
      exec: "tutor",
      startTime: "15s",
      tags: { workload: "ai" },
    },
    scoring: {
      executor: "constant-vus",
      vus: SCORING_VUS,
      duration: __ENV.DURATION || "2m",
      exec: "scoring",
      startTime: "20s",
      tags: { workload: "ai" },
    },
  },
  thresholds: {
    "http_req_failed{workload:navigation}": ["rate<0.01"],
    "http_req_duration{expected:read}": ["p(95)<1000"],
  },
};

function tokenFor() {
  if (cachedToken) {
    return cachedToken;
  }
  const user = USERS[__VU % USERS.length];
  const response = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: user, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  );
  const cookie = response.cookies.access_token;
  cachedToken = cookie && cookie.length ? cookie[0].value : null;
  return cachedToken;
}

function startSession(headers) {
  // A fresh conversation per iteration: the tutor caps turns per step, and the
  // point of this scenario is sustained concurrent AI work, not one long chat.
  const response = http.post(`${BASE_URL}/api/sessions/start`, JSON.stringify({ case_id: 1 }), {
    headers: { ...headers, "Content-Type": "application/json" },
  });
  return response.status === 200 ? response.json("id") : null;
}

export function navigate() {
  const token = tokenFor();
  if (!token) return;
  const headers = { Cookie: `access_token=${token}` };
  const reads = ["/api/student/dashboard", "/api/student/pathway", "/api/student/competency", "/api/knowledge"];
  for (const path of reads) {
    const response = http.get(`${BASE_URL}${path}`, { headers, tags: { expected: "read" } });
    readLatency.add(response.timings.duration);
    check(response, { "navigation read is 200": (r) => r.status === 200 });
    sleep(0.3);
  }
  sleep(1);
}

export function tutor() {
  const token = tokenFor();
  if (!token) return;
  const headers = { Cookie: `access_token=${token}`, "Content-Type": "application/json" };
  const sessionId = startSession(headers);
  if (!sessionId) return;
  const answer = http.post(
    `${BASE_URL}/api/sessions/${sessionId}/answers`,
    JSON.stringify({ step: "differential_diagnosis", answer_text: ANSWER }),
    { headers },
  );
  check(answer, { "answer saved": (r) => r.status === 200 });
  const started = Date.now();
  const response = http.post(
    `${BASE_URL}/api/sessions/${sessionId}/tutor`,
    JSON.stringify({ step: "differential_diagnosis" }),
    { headers, timeout: "150s" },
  );
  aiLatency.add(Date.now() - started);
  // A provider failure must degrade, not surface as a 5xx.
  check(response, { "tutor degraded instead of failing": (r) => r.status === 200 || r.status === 429 });
  sleep(1);
}

export function scoring() {
  const token = tokenFor();
  if (!token) return;
  const headers = { Cookie: `access_token=${token}`, "Content-Type": "application/json" };
  const sessionId = startSession(headers);
  if (!sessionId) return;
  for (const step of ["key_information", "initial_diagnosis", "differential_diagnosis", "examination", "treatment"]) {
    http.post(`${BASE_URL}/api/sessions/${sessionId}/answers`, JSON.stringify({ step, answer_text: ANSWER }), {
      headers,
    });
  }
  const started = Date.now();
  const response = http.post(`${BASE_URL}/api/sessions/${sessionId}/submit`, null, { headers, timeout: "180s" });
  aiLatency.add(Date.now() - started);
  check(response, { "submit degraded instead of failing": (r) => r.status === 200 });
  sleep(2);
}
