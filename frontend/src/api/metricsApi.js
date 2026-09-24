import { request } from './client';

export async function fetchMetrics() {
  return request('/api/metrics');
}
