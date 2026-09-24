import { request } from './client';

export async function fetchCaseGraph(caseId) {
  return request(`/api/graph/${encodeURIComponent(caseId)}`);
}
