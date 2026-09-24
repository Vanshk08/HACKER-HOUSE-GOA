import { request } from './client';

export async function fetchHealth() {
  return request('/api/health');
}
