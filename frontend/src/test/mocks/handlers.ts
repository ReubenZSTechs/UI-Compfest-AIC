import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/config/env";
import { digitalTwinFixture } from "./fixtures/digitalTwin.fixture";

export const handlers = [
  http.get(`${API_BASE_URL}/digital-twin`, () => {
    return HttpResponse.json(digitalTwinFixture);
  }),

  http.get(`${API_BASE_URL}/digital-twin/assets`, () => {
    return HttpResponse.json(digitalTwinFixture.assets);
  }),

  http.get(`${API_BASE_URL}/digital-twin/workers`, () => {
    return HttpResponse.json(digitalTwinFixture.workers);
  }),

  http.get(`${API_BASE_URL}/digital-twin/job-desks`, () => {
    return HttpResponse.json(digitalTwinFixture.job_desks);
  }),

  http.get(`${API_BASE_URL}/digital-twin/compatibility-matrix`, () => {
    return HttpResponse.json(digitalTwinFixture.llm_compatibility_and_evaluations);
  }),
];