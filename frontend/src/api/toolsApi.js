import { request } from './client';

export async function fetchTools() {
  return request('/api/tools');
}
